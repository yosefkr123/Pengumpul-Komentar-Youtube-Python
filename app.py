from flask import Flask, render_template, request, send_file, session
import pandas as pd
import io
import re
from youtube_comment_downloader import YoutubeCommentDownloader
from datetime import datetime
import traceback
import requests
from bs4 import BeautifulSoup
import emoji

app = Flask(__name__)
app.secret_key = 'supersecretkey123'
app.config['MAX_COMMENTS'] = 10000  # Increased limit

def remove_emojis(text):
    return emoji.replace_emoji(text, replace='') if text else text

def clean_comment_text(text, for_display=False):
    # Only remove emojis when downloading
    if not for_display:
        text = remove_emojis(text)
    # Clean other special characters
    text = re.sub(r'http[s]?://\S+', '', text)
    text = re.sub(r'[^\w\s.,!?\'"-]', '', text)
    return text.strip()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        video_url = request.form['video_url']
        try:
            comment_count = int(request.form.get('comment_count', 20))
            if comment_count <= 0:
                comment_count = app.config['MAX_COMMENTS']
        except:
            comment_count = app.config['MAX_COMMENTS']
        
        video_id = extract_video_id(video_url)
        if not video_id:
            return render_template('index.html', error="Invalid YouTube URL")
        
        try:
            channel_name = get_channel_name(video_id)
            comments = get_youtube_comments(video_id, comment_count)
            
            if not comments:
                return render_template('index.html', 
                                    error="No comments found. Possible reasons:<br>"
                                          "1. Video has no public comments<br>"
                                          "2. Comments are restricted<br>"
                                          "3. YouTube temporary restriction")
            
            session['comments_data'] = comments
            session['video_info'] = {
                'url': video_url,
                'channel': channel_name,
                'count': len(comments)
            }
            
            return render_template('results.html', 
                                comments=comments,
                                video_url=video_url,
                                channel_name=channel_name,
                                comment_count=len(comments))
            
        except Exception as e:
            print(f"Error: {str(e)}")
            print(traceback.format_exc())
            return render_template('index.html', 
                                error=f"Error fetching comments: {str(e)}")
    
    return render_template('index.html')

def extract_video_id(url):
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtu\.be\/([a-zA-Z0-9_-]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def get_channel_name(video_id):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        channel_element = soup.find("span", itemprop="author")
        if channel_element:
            channel_name = channel_element.find("link", itemprop="name")["content"]
            return channel_name
        return "Unknown Channel"
    except:
        return "Unknown Channel"

def get_youtube_comments(video_id, max_comments):
    downloader = YoutubeCommentDownloader()
    comments = []
    
    try:
        generator = downloader.get_comments_from_url(
            f'https://www.youtube.com/watch?v={video_id}',
            sort_by=1,  # Newest first
        )
        
        for count, comment in enumerate(generator, 1):
            if count > max_comments and max_comments != app.config['MAX_COMMENTS']:
                break
                
            try:
                # Skip comments with links
                if 'http://' in comment.get('text', '').lower() or 'https://' in comment.get('text', '').lower():
                    continue
                    
                # Clean and process comment (for display)
                cleaned_text = clean_comment_text(comment.get('text', ''), for_display=True)
                if not cleaned_text:  # Skip empty comments after cleaning
                    continue
                
                # Format timestamp
                timestamp = 'N/A'
                if 'time' in comment:
                    try:
                        timestamp = datetime.strptime(comment['time'], '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        timestamp = comment['time']
                elif 'timestamp' in comment:
                    timestamp = datetime.fromtimestamp(comment['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                
                comments.append({
                    'author': comment.get('author', 'Unknown'),
                    'text': cleaned_text,
                    'time': timestamp,
                    'likes': comment.get('votes', 0),
                    'replies': comment.get('reply_count', 0)
                })
                
            except Exception as e:
                print(f"Error processing comment {count}: {str(e)}")
                continue
    
    except Exception as e:
        print(f"Error in comment generator: {str(e)}")
        return None
    
    return comments if comments else None

@app.route('/download/<format>')
def download_comments(format):
    if 'comments_data' not in session or not session['comments_data']:
        return "Comment data not available", 400
    
    try:
        comments = session['comments_data']
        video_info = session.get('video_info', {})
        
        # Create a deep copy of comments and clean them for download
        download_comments = []
        for comment in comments:
            download_comments.append({
                'author': comment['author'],
                'text': clean_comment_text(comment['text'], for_display=False),
                'time': comment['time'],
                'likes': comment['likes'],
                'replies': comment['replies']
            })
        
        df = pd.DataFrame(download_comments)
        
        if format == 'csv':
            output = io.StringIO()
            df.to_csv(output, index=False, encoding='utf-8')
            output.seek(0)
            
            return send_file(
                io.BytesIO(output.getvalue().encode('utf-8')),
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'youtube_comments_{video_info.get("channel", "unknown")}.csv'
            )
            
        elif format == 'xlsx':
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Comments')
                if video_info:
                    info_df = pd.DataFrame({
                        'Video URL': [video_info.get('url', '')],
                        'Channel': [video_info.get('channel', '')],
                        'Total Comments': [video_info.get('count', 0)]
                    })
                    info_df.to_excel(writer, index=False, sheet_name='Video Info')
            output.seek(0)
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=f'youtube_comments_{video_info.get("channel", "unknown")}.xlsx'
            )
        else:
            return "Invalid format", 400
    
    except Exception as e:
        return f"Error preparing download: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)