import feedparser
import google.generativeai as genai
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import time
import hashlib

# ============================================
# CONFIGURATION - CHOOSE YOUR STRATEGY HERE
# ============================================

# Strategy choice: "limit_articles", "limit_feeds", or "deduplicate"
STRATEGY = "limit_articles"  # Change this to test different strategies

# Strategy 1: Limit articles per day (set to None for unlimited)
MAX_ARTICLES_PER_DAY = None  # Set to a number like 15 if you want a limit, None for unlimited

# Strategy 2: Reduce number of feeds
RSS_FEEDS_ALL = [
    'https://www.theprp.com/feed',
    'https://www.nytimes.com/services/xml/rss/nyt/HomePage.xml',
    'https://www.robotitus.com/feed/',
    'https://www.guardian.co.uk/technology/artificialintelligenceai/rss',
    'https://www.eldiario.es/rss/',
    'https://www.iflscience.com/rss/ifls-latest-rss.xml',
    'https://futurism.com/feed',
    'https://maldita.es/feed/'
]

# For Strategy 2: Only use first 5 feeds
RSS_FEEDS_LIMITED = RSS_FEEDS_ALL[:5]

# For other strategies: Use all feeds
RSS_FEEDS = RSS_FEEDS_LIMITED if STRATEGY == "limit_feeds" else RSS_FEEDS_ALL

# ============================================
# END CONFIGURATION
# ============================================

def get_recent_articles():
    """Get articles from the last 24 hours"""
    articles = []
    cutoff_time = datetime.now() - timedelta(days=1)
    
    for feed_url in RSS_FEEDS:
        try:
            print(f"Fetching from: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    else:
                        continue
                    
                    if pub_date > cutoff_time:
                        article = {
                            'title': entry.title,
                            'description': entry.get('description', ''),
                            'link': entry.link,
                            'source': feed.feed.title,
                            'date': pub_date
                        }
                        articles.append(article)
                        
                except Exception as e:
                    print(f"Error processing article: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error fetching {feed_url}: {e}")
            continue
    
    articles.sort(key=lambda x: x['date'], reverse=True)
    return articles

def remove_duplicate_articles(articles):
    """Remove duplicate articles based on similar titles"""
    seen = {}
    unique_articles = []
    
    for article in articles:
        # Create a hash of the title (normalized)
        title_hash = hashlib.md5(article['title'].lower().strip().encode()).hexdigest()
        
        if title_hash not in seen:
            seen[title_hash] = True
            unique_articles.append(article)
        else:
            print(f"Skipping duplicate: {article['title']}")
    
    return unique_articles

def apply_strategy(articles):
    """Apply the selected strategy to articles"""
    
    if STRATEGY == "limit_articles":
        print(f"\nStrategy: LIMIT ARTICLES")
        if MAX_ARTICLES_PER_DAY is not None:
            print(f"Processing max {MAX_ARTICLES_PER_DAY} articles")
            return articles[:MAX_ARTICLES_PER_DAY]
        else:
            print(f"Processing ALL {len(articles)} articles (unlimited)")
            return articles
    
    elif STRATEGY == "limit_feeds":
        print(f"\nStrategy: LIMIT FEEDS")
        print(f"Using only {len(RSS_FEEDS)} feeds (reduced from {len(RSS_FEEDS_ALL)})")
        return articles[:20]  # Still limit to avoid API overload
    
    elif STRATEGY == "deduplicate":
        print(f"\nStrategy: DEDUPLICATE + LIMIT")
        print(f"Found {len(articles)} total articles")
        unique = remove_duplicate_articles(articles)
        print(f"After deduplication: {len(unique)} unique articles")
        return unique[:MAX_ARTICLES_PER_DAY]
    
    return articles

def summarize_article(article):
    """Summarize article using Google Gemini"""
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        
        if not api_key:
            print("ERROR: GEMINI_API_KEY not found in environment variables!")
            return f"ERROR: API key no configurado"
        
        # Check if article has content
        content = article['description'][:800]
        if not content or len(content.strip()) < 20:
            print(f"Warning: Article has no/minimal content")
            return f"No hay contenido disponible para resumir"
        
        genai.configure(api_key=api_key)
        
        # Use the correct model name for Gemini API
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""Resume este artículo de noticias en español en 4-5 puntos clave. 
Sé conciso pero completo.

Título: {article['title']}
Contenido: {content}"""
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        print(f"Error summarizing article: {type(e).__name__}: {str(e)}")
        return f"Error: {type(e).__name__} - {str(e)}"

def send_email(summaries, strategy_info):
    """Send email with news summaries"""
    try:
        sender_email = os.getenv('GMAIL_EMAIL')
        sender_password = os.getenv('GMAIL_PASSWORD')
        recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = f"Resumen Diario de Noticias - {datetime.now().strftime('%d/%m/%Y')}"
        
        body = f"""
        <html>
        <body>
        <h2>Resumen Diario de Noticias</h2>
        <p><strong>Fecha:</strong> {datetime.now().strftime('%d de %B de %Y')}</p>
        <p><strong>Estrategia:</strong> {strategy_info}</p>
        <p><strong>Artículos resumidos:</strong> {len(summaries)}</p>
        <hr>
        """
        
        for i, summary in enumerate(summaries, 1):
            body += f"""
            <h3>{i}. {summary['title']}</h3>
            <p><strong>Fuente:</strong> {summary['source']}</p>
            <p><strong>Fecha:</strong> {summary['date'].strftime('%d/%m/%Y %H:%M')}</p>
            <p>{summary['summary']}</p>
            <p><a href="{summary['link']}">Leer artículo completo</a></p>
            <hr>
            """
        
        body += """
        </body>
        </html>
        """
        
        message.attach(MIMEText(body, "html"))
        
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
        
        print("Email sent successfully!")
        
    except Exception as e:
        print(f"Error sending email: {e}")

def main():
    """Main function"""
    print("Starting news aggregation with Google Gemini...")
    
    articles = get_recent_articles()
    print(f"\nTotal articles found: {len(articles)}")
    
    if not articles:
        print("No recent articles found")
        return
    
    # Apply selected strategy
    filtered_articles = apply_strategy(articles)
    print(f"Articles to summarize: {len(filtered_articles)}\n")
    
    if not filtered_articles:
        print("No articles to process after applying strategy")
        return
    
    summaries = []
    for idx, article in enumerate(filtered_articles, 1):
        print(f"[{idx}/{len(filtered_articles)}] Summarizing: {article['title'][:60]}...")
        summary = summarize_article(article)
        
        summaries.append({
            'title': article['title'],
            'source': article['source'],
            'date': article['date'],
            'summary': summary,
            'link': article['link']
        })
        
        time.sleep(1)
    
    if summaries:
        strategy_info = f"{STRATEGY.upper()} - {len(filtered_articles)} articles"
        send_email(summaries, strategy_info)
    else:
        print("No summaries to send")

if __name__ == "__main__":
    main()
