# <img src='logo/logo.png' width='512'/>
### Discord music bot written in Python with Disnake.
<br/>

## Installation
<table>
	<tr>
		<td><h3>Dependencies</h3></td>
		<td colspan='2'/>
		<td colspan='4'>pip<br/>You can install these packages using<br/>'pip install -r requirements'</td>
		<td colspan='2'>On Linux you may also have to install these packages</td>
	</tr>
	<tr>
		<td>Package</td>
		<td>Python</td><td>ffmpeg & ffprobe</td>
		<td>Disnake</td><td>yt-dlp</td><td>Spotipy</td><td>PyNaCl</td>
		<td>libffi-dev</td><td>openssl / libssl-dev</td>
	</tr>
	<tr>
		<td>Tested on version</td>
		<td>3.11.0</td><td>4.4.2</td>
		<td>2.7.0</td><td>2022.11.11</td><td>2.22.0</td>
	</tr>
</table>

Clone the repo, install required packages and after configuration run the 'SodiumMusic.py' file.

## Configuration
Just fill the 'config.sm' file with correct values.
### Effects
Effects in config are the ffmpeg's -af parameter. If the effect doesn't affect the playback speed, you just have to include it as a string. Ex.:
	
	'8d': 'apulsator = hz = 0.125'

Otherwise you must include it's factor as a second tuple element:

	'nightcore': ('asetrate = 48000 * 1.25', 1.25)

## ToDo:
- implementation of the 'back' command

### Known problems:
- Titles of Soundcloud playlist entries are not available in the queue preview because of this issue: https://github.com/yt-dlp/yt-dlp/issues/1871
- Some tracks from Spotify playlists (with indexes over 100) are being returned incorrectly (non-existing in playlist instead of correct ones)

## If you encounter any bugs or errors, feel free to inform me about them in the 'Issues' section ッ
