from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import time
from datetime import datetime, timedelta
from typing import Optional
import models, database, cache, utils
from pydantic import BaseModel, HttpUrl
import qrcode
from io import BytesIO
from fastapi.responses import StreamingResponse

## Creates the FastAPI app with metadata
app = FastAPI(
    title="URL Shortener API",
    description="A scalable URL shortening service with analytics",
    version="1.0.0"
)

## CORS middleware: Enables cross-origin requests(so a frontend can call this API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

## Database dependency
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

## Pydantic models for request/response
class URLCreate(BaseModel):
    url: HttpUrl
    custom_code: Optional[str] = None
    expires_in_days: Optional[int] = None

class URLResponse(BaseModel):
    original_url: str
    short_code: str
    short_url: str
    created_at: datetime
    expires_at: Optional[datetime]
    click_count: int

class AnalyticsResponse(BaseModel):
    short_code: str
    original_url: str
    total_clicks: int
    created_at: datetime
    recent_clicks: list

## Rate Limiter to prevent overload; Allow max_requests per window_seconds
def rate_limit(request: Request, max_requests: int = 10, window_seconds: int = 60):
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"
    
    current_count = cache.redis_client.get(key)
    
    if current_count and int(current_count) >= max_requests:
        raise HTTPException(status_code=429, detail="Too many requests. Try again later.")
    
    # Increment counter
    pipe = cache.redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    pipe.execute()

# ==================== ENDPOINTS ====================

@app.get("/", response_class=HTMLResponse)

## Returns a simple HTML page to enter URLs and get shortened links
async def read_root():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>URL Shortener</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 600px;
                margin: 50px auto;
                padding: 20px;
                background: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            h1 { color: #333; }
            input {
                width: 100%;
                padding: 12px;
                margin: 10px 0;
                border: 1px solid #ddd;
                border-radius: 5px;
                box-sizing: border-box;
            }
            button {
                width: 100%;
                padding: 12px;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
            }
            button:hover { background: #0056b3; }
            #result {
                margin-top: 20px;
                padding: 15px;
                background: #e7f3ff;
                border-radius: 5px;
                display: none;
            }
            .short-url {
                color: #007bff;
                font-weight: bold;
                word-break: break-all;
            }
            .error {
                background: #ffe7e7;
                color: #d00;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>URL Shortener</h1>
            <p>Shorten your long URLs instantly!</p>
            
            <input type="url" id="urlInput" placeholder="Enter your long URL here" required>
            <input type="text" id="customCode" placeholder="Custom code (optional)">
            <input type="number" id="expiresIn" placeholder="Expires in days (optional)" min="1">
            <button onclick="shortenURL()">Shorten URL</button>
            
            <div id="result"></div>
        </div>

        <script>
            async function shortenURL() {
                const url = document.getElementById('urlInput').value;
                const customCode = document.getElementById('customCode').value;
                const expiresIn = document.getElementById('expiresIn').value;
                const resultDiv = document.getElementById('result');
                
                if (!url) {
                    resultDiv.className = 'error';
                    resultDiv.innerHTML = 'Please enter a URL';
                    resultDiv.style.display = 'block';
                    return;
                }
                
                const payload = { url: url };
                if (customCode) payload.custom_code = customCode;
                if (expiresIn) payload.expires_in_days = parseInt(expiresIn);
                
                try {
                    const response = await fetch('/shorten', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    
                    const data = await response.json();
                    
                    if (response.ok) {
                        resultDiv.className = '';
                        resultDiv.innerHTML = `
                            URL shortened successfully!<br><br>
                            <strong>Short URL:</strong><br>
                            <a href="${data.short_url}" target="_blank" class="short-url">${data.short_url}</a><br><br>
                            <small>Clicks: ${data.click_count} | Created: ${new Date(data.created_at).toLocaleString()}</small>
                        `;
                    } else {
                        resultDiv.className = 'error';
                        resultDiv.innerHTML = `Error: ${data.detail}`;
                    }
                    
                    resultDiv.style.display = 'block';
                } catch (error) {
                    resultDiv.className = 'error';
                    resultDiv.innerHTML = `Error: ${error.message}`;
                    resultDiv.style.display = 'block';
                }
            }
            
            // Allow Enter key to submit
            document.getElementById('urlInput').addEventListener('keypress', (e) => {
                if (e.key === 'Enter') shortenURL();
            });
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/shorten", response_model=URLResponse)

## Creates a shortened URL
async def shorten_url(url_data: URLCreate, request: Request, db: Session = Depends(get_db)):
    ## set the rate limit to 10 requests per minute
    rate_limit(request, max_requests=10, window_seconds=60)

    ## Check if custom code already exists
    if url_data.custom_code:
        existing = db.query(models.URL).filter(models.URL.short_code == url_data.custom_code).first()
        if existing:
            raise HTTPException(status_code=400, detail="Custom code already exists")
        short_code = url_data.custom_code
    else:
        ## Generate unique short code
        short_code = utils.generate_short_code()
        while db.query(models.URL).filter(models.URL.short_code == short_code).first():
            short_code = utils.generate_short_code()
    
    ## Calculate expiration date
    expires_at = None
    if url_data.expires_in_days:
        expires_at = datetime.now() + timedelta(days=url_data.expires_in_days)
    
    ## Create URL entry
    db_url = models.URL(
        original_url=str(url_data.url),
        short_code=short_code,
        expires_at=expires_at
    )
    db.add(db_url)
    db.commit()
    db.refresh(db_url)
    
    ## Cache it
    cache.set_url(short_code, str(url_data.url), expires_at)
    
    ## Build short URL
    base_url = str(request.base_url).rstrip('/')
    short_url = f"{base_url}/{short_code}"
    
    return URLResponse(
        original_url=db_url.original_url,
        short_code=db_url.short_code,
        short_url=short_url,
        created_at=db_url.created_at,
        expires_at=db_url.expires_at,
        click_count=db_url.click_count
    )


@app.get("/analytics/{short_code}", response_model=AnalyticsResponse)

## Get analytics for a shortened URL
async def get_analytics(short_code: str, db: Session = Depends(get_db)):
    
    ## get the URL from the database
    db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()
    if not db_url:
        raise HTTPException(status_code=404, detail="URL not found")
    
    ## Get recent clicks (last 10)
    recent_clicks = db.query(models.Click)\
        .filter(models.Click.url_id == db_url.id)\
        .order_by(models.Click.clicked_at.desc())\
        .limit(10)\
        .all()
    
    clicks_data = [
        {
            "clicked_at": click.clicked_at,
            "ip_address": click.ip_address,
            "user_agent": click.user_agent[:50] + "..." if len(click.user_agent) > 50 else click.user_agent,
            "referrer": click.referrer
        }
        for click in recent_clicks
    ]
    
    return AnalyticsResponse(
        short_code=db_url.short_code,
        original_url=db_url.original_url,
        total_clicks=db_url.click_count,
        created_at=db_url.created_at,
        recent_clicks=clicks_data
    )

@app.get("/api/stats")

## Get overall system statistics
async def get_stats(db: Session = Depends(get_db)):
    
    total_urls = db.query(models.URL).count()
    total_clicks = db.query(models.Click).count()
    
    ## Most clicked URLs
    top_urls = db.query(models.URL)\
        .order_by(models.URL.click_count.desc())\
        .limit(5)\
        .all()
    
    return {
        "total_urls": total_urls,
        "total_clicks": total_clicks,
        "top_urls": [
            {
                "short_code": url.short_code,
                "original_url": url.original_url,
                "clicks": url.click_count
            }
            for url in top_urls
        ]
    }

@app.delete("/api/urls/{short_code}")

## Delete a shortened URL
async def delete_url(short_code: str, db: Session = Depends(get_db)):
    # Get the URL from database
    db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()
    if not db_url:
        raise HTTPException(status_code=404, detail="URL not found")
    
    db.delete(db_url)
    db.commit()
    
    # Remove from cache
    cache.delete_url(short_code)
    
    return {"message": "URL deleted successfully"}

## Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(),
        "database": "connected" if database.engine else "disconnected",
        "cache": "connected" if cache.redis_client else "disconnected"
    }

@app.get("/qr/{short_code}")

## Generate QR code for shortened URL
async def get_qr_code(short_code: str, request: Request, db: Session = Depends(get_db)):
    
    db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()
    if not db_url:
        raise HTTPException(status_code=404, detail="URL not found")
    
    ## Generate QR code
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(f"{str(request.base_url).rstrip('/')}/{short_code}")
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    ## Return as PNG
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return StreamingResponse(buf, media_type="image/png")

## Redirect route is declared last so fixed paths like /health are matched first
@app.get("/{short_code}")

## Redirect to original URL and track analytics
async def redirect_to_url(short_code: str, request: Request, db: Session = Depends(get_db)):
    
    ## Try cache first
    cached_url = cache.get_url(short_code)
    if cached_url:
        original_url = cached_url
    else:
        ## Get from database
        db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()
        if not db_url:
            raise HTTPException(status_code=404, detail="URL not found")
        
        ## Check if expired
        if db_url.expires_at and db_url.expires_at < datetime.now():
            raise HTTPException(status_code=410, detail="URL has expired")
        
        original_url = db_url.original_url
        
        ## Update cache
        cache.set_url(short_code, original_url, db_url.expires_at)
    
    ## Track click (async in background)
    db_url = db.query(models.URL).filter(models.URL.short_code == short_code).first()
    if db_url:
        db_url.click_count += 1
        
        ## Record click details
        click = models.Click(
            url_id=db_url.id,
            ip_address=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
            referrer=request.headers.get("referer", "")
        )
        db.add(click)
        db.commit()
    
    return RedirectResponse(url=original_url, status_code=307)