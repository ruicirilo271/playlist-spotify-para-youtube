from flask import Flask, request, redirect, render_template, session, url_for
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

app = Flask(__name__)
app.secret_key = "um_segredo_seguro"
app.config['SESSION_COOKIE_NAME'] = 'spotify_youtube_session'

# --- Configurações Spotify ---
SPOTIPY_CLIENT_ID = '62105638db7042199049e9040993fd79'
SPOTIPY_CLIENT_SECRET = '759b02d8c5dc438f99317ceb9c1cac4b'
SPOTIPY_REDIRECT_URI = 'https://dee4-109-48-203-219.ngrok-free.app/spotify_callback'
SPOTIFY_SCOPE = 'playlist-read-private'

# --- Escopos YouTube ---
YOUTUBE_SCOPES = ['https://www.googleapis.com/auth/youtube']
YOUTUBE_REDIRECT_URI = 'https://dee4-109-48-203-219.ngrok-free.app/youtube_callback'

@app.route('/')
def index():
    return render_template("index.html")

@app.route('/start')
def start():
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SPOTIFY_SCOPE
    )
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/spotify_callback')
def spotify_callback():
    sp_oauth = SpotifyOAuth(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope=SPOTIFY_SCOPE
    )
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['spotify_token'] = token_info['access_token']
    return redirect(url_for('youtube_login'))

@app.route('/youtube_login')
def youtube_login():
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=YOUTUBE_SCOPES,
        redirect_uri=YOUTUBE_REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(prompt='consent')
    session['state'] = state
    # Não guardar flow.to_json() pois não existe
    return redirect(auth_url)

@app.route('/youtube_callback')
def youtube_callback():
    state = session.get('state') or request.args.get('state')
    flow = Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=YOUTUBE_SCOPES,
        redirect_uri=YOUTUBE_REDIRECT_URI,
        state=state
    )
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session['youtube_credentials'] = credentials_to_dict(credentials)
    return redirect(url_for('formulario'))

@app.route('/formulario')
def formulario():
    return '''
        <form action="/process" method="post">
            URL da playlist do Spotify: <input type="text" name="playlist_url"><br>
            Nome da playlist no YouTube: <input type="text" name="playlist_name"><br>
            <input type="submit" value="Criar Playlist no YouTube">
        </form>
    '''

@app.route('/process', methods=['POST'])
def process():
    playlist_url = request.form.get("playlist_url")
    yt_playlist_name = request.form.get("playlist_name")

    # Spotify
    sp = Spotify(auth=session['spotify_token'])
    playlist_id = playlist_url.split("/")[-1].split("?")[0]
    results = sp.playlist_tracks(playlist_id)
    tracks = [f"{item['track']['name']} {item['track']['artists'][0]['name']}" for item in results['items']]

    # YouTube
    creds = Credentials(**session['youtube_credentials'])
    youtube = build("youtube", "v3", credentials=creds)

    yt_playlist = youtube.playlists().insert(
        part="snippet,status",
        body={
            "snippet": {"title": yt_playlist_name},
            "status": {"privacyStatus": "private"}
        }
    ).execute()
    playlist_id = yt_playlist["id"]

    adicionadas = []
    for track in tracks:
        res = youtube.search().list(q=track, part="snippet", maxResults=1, type="video").execute()
        if not res['items']:
            continue
        video_id = res['items'][0]['id']['videoId']
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id}
                }
            }
        ).execute()
        adicionadas.append(track)

    return f"✅ Playlist criada com {len(adicionadas)} músicas no YouTube!"

def credentials_to_dict(credentials):
    return {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

if __name__ == '__main__':
    app.run(port=5000, debug=True)
