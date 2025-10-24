import feedparser
import requests
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import time
import json

# CONFIGURATION
RSS_FEEDS = [
    'https://www.theprp.com/feed',
    'https://www.robotitus.com/feed/',
    'https://www.guardian.co.uk/technology/artificialintelligenceai/rss',
    'https://www.eldiario.es/rss/',
    'https://www.iflscience.com/rss/ifls-latest-rss.xml',
    'https://futurism.com/feed',
    'https://maldita.es/feed/',
    'https://www.europapress.es/rss/rss.aspx?ch=298',
    'https://www.europapress.es/rss/rss.aspx?ch=66',
    'https://www.europapress.es/rss/rss.aspx?ch=69'
]

# Hugging Face API endpoint
HF_API_URL = "https://api-inference.huggingface.co/models/facebook/bart-large-cnn"

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
                    continue
                    
        except Exception as e:
            print(f"Error fetching {feed_url}: {e}")
            continue
    
    articles.sort(key=lambda x: x['date'], reverse=True)
    return articles

def summarize_with_huggingface(text, api_key):
    """Summarize text using Hugging Face API"""
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Limit text length for API
    text = text[:1000]
    
    payload = {
        "inputs": text,
        "parameters": {
            "max_length": 130,
            "min_length": 30,
            "do_sample": False
        }
    }
    
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if isinstance(result, list) and len(result) > 0:
                return result[0].get('summary_text', '')
        elif response.status_code == 503:
            # Model is loading, wait and retry
            print("Model loading, waiting 20 seconds...")
            time.sleep(20)
            response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    return result[0].get('summary_text', '')
        
        print(f"API Error: {response.status_code} - {response.text}")
        return None
        
    except Exception as e:
        print(f"Request error: {e}")
        return None

def translate_to_spanish(text):
    """Simple translation prompting (returns English summary with Spanish note)"""
    # Since we're using a free API, we'll return English summaries
    # You could add a translation step here if needed
    return text

def summarize_article(article):
    """Summarize article using Hugging Face"""
    try:
        api_key = os.getenv('HUGGINGFACE_API_KEY')
        
        if not api_key:
            print("ERROR: HUGGINGFACE_API_KEY not found!")
            return "ERROR: API key no configurado"
        
        # Get content
        content = article.get('description', article['title'])
        if not content or len(content.strip()) < 20:
            return "No hay contenido disponible"
        
        # Clean HTML tags if present
        import re
        content = re.sub('<[^<]+?>', '', content)
        
        # Combine title and content for better context
        full_text = f"{article['title']}. {content}"
        
        # Get summary from Hugging Face
        summary = summarize_with_huggingface(full_text, api_key)
        
        if summary:
            # Add Spanish prefix since summary will be in English
            return f"[Resumen en inglés] {summary}"
        else:
            return "No se pudo generar resumen"
        
    except Exception as e:
        print(f"Error summarizing: {e}")
        return f"Error: {str(e)}"

def send_email(summaries):
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
        <p><strong>Artículos resumidos:</strong> {len(summaries)}</p>
        <p><em>Nota: Los resúmenes están en inglés (limitación de la API gratuita)</em></p>
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
    print("Starting news aggregation with Hugging Face...")
    
    articles = get_recent_articles()
    print(f"\nTotal articles found: {len(articles)}")
    
    if not articles:
        print("No recent articles found")
        return
    
    print(f"Articles to summarize: {len(articles)}\n")
    
    summaries = []
    successful = 0
    
    for idx, article in enumerate(articles, 1):
        print(f"[{idx}/{len(articles)}] Summarizing: {article['title'][:60]}...")
        summary = summarize_article(article)
        
        if summary and "ERROR" not in summary and "No se pudo" not in summary:
            summaries.append({
                'title': article['title'],
                'source': article['source'],
                'date': article['date'],
                'summary': summary,
                'link': article['link']
            })
            successful += 1
        
        # Rate limiting - Hugging Face free tier has limits
        time.sleep(2)
    
    print(f"\nSuccessfully summarized: {successful}/{len(articles)}")
    
    if summaries:
        send_email(summaries)
    else:
        print("No summaries to send")

if __name__ == "__main__":
    main()
