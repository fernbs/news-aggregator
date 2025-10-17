import feedparser
import openai
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os
import time
import re

# Configuration
RSS_FEEDS = [
    'https://www.theprp.com/feed',
    'https://www.nytimes.com/services/xml/rss/nyt/HomePage.xml',
    'https://www.robotitus.com/feed/',
    'https://www.europapress.es/rss/rss.aspx?ch=298',
    'https://www.guardian.co.uk/technology/artificialintelligenceai/rss',
    'https://www.eldiario.es/rss/',
    'https://www.iflscience.com/rss/ifls-latest-rss.xml',
    'https://futurism.com/feed',
    'https://maldita.es/feed/',
    'https://feeds.feedburner.com/trendwatching',
    'https://www.huffpost.com/section/front-page/feed'
]

def get_recent_articles():
    """Get articles from the last 24 hours"""
    articles = []
    cutoff_time = datetime.now() - timedelta(days=1)
    
    for feed_url in RSS_FEEDS:
        try:
            print(f"Fetching from: {feed_url}")
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                # Try to parse the publication date
                try:
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        pub_date = datetime(*entry.published_parsed[:6])
                    elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                        pub_date = datetime(*entry.updated_parsed[:6])
                    else:
                        continue  # Skip if no date available
                    
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
    
    return articles

def summarize_article(article):
    """Summarize article using ChatGPT API"""
    try:
        # Set up OpenAI client
        openai.api_key = os.getenv('OPENAI_API_KEY')
        
        prompt = f"""
        Resumir el siguiente artículo de noticias en español con 6-8 frases. 
        Incluir todos los detalles importantes y datos clave.
        Si el artículo está en inglés, traducir y resumir en español.
        
        Título: {article['title']}
        Contenido: {article['description']}
        Fuente: {article['source']}
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un periodista experto que crea resúmenes concisos pero completos de noticias en español."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error summarizing article: {e}")
        return f"Error al resumir: {article['title']}"

def send_email(summaries):
    """Send email with news summaries"""
    try:
        sender_email = os.getenv('GMAIL_EMAIL')
        sender_password = os.getenv('GMAIL_PASSWORD')
        recipient_email = os.getenv('RECIPIENT_EMAIL')
        
        # Create message
        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = f"Resumen Diario de Noticias - {datetime.now().strftime('%d/%m/%Y')}"
        
        # Create email body
        body = f"""
        <html>
        <body>
        <h2>Resumen Diario de Noticias</h2>
        <p><strong>Fecha:</strong> {datetime.now().strftime('%d de %B de %Y')}</p>
        <p><strong>Artículos encontrados:</strong> {len(summaries)}</p>
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
        
        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
        
        print("Email sent successfully!")
        
    except Exception as e:
        print(f"Error sending email: {e}")

def main():
    """Main function"""
    print("Starting news aggregation...")
    
    # Get recent articles
    articles = get_recent_articles()
    print(f"Found {len(articles)} recent articles")
    
    if not articles:
        print("No recent articles found")
        return
    
    # Summarize articles
    summaries = []
    for article in articles:
        print(f"Summarizing: {article['title']}")
        summary = summarize_article(article)
        
        summaries.append({
            'title': article['title'],
            'source': article['source'],
            'date': article['date'],
            'summary': summary,
            'link': article['link']
        })
        
        time.sleep(1)  # Rate limiting
    
    # Send email
    if summaries:
        send_email(summaries)
    else:
        print("No summaries to send")

if __name__ == "__main__":
    main()
