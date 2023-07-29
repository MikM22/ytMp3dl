import os
import sys
import re
import argparse
import subprocess
from zipfile import ZipFile

try:
    import yt_dlp
except ImportError as e:
    sys.exit("You need yt-dlp! Try running pip install yt-dlp.")

try:
    import requests
except ImportError as e:
    sys.exit("You need requests! Try running pip install requests.")

mp4 = False
current_directory = os.path.dirname(os.path.abspath(sys.argv[0]))

def get_downloads_path():
    if os.name == 'nt':
        import ctypes
        from ctypes import windll, wintypes
        from uuid import UUID

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8)
            ]

            def __init__(self, uuidstr):
                uuid = UUID(uuidstr)
                ctypes.Structure.__init__(self)
                self.Data1, self.Data2, self.Data3, \
                self.Data4[0], self.Data4[1], rest = uuid.fields
                for i in range(2, 8):
                    self.Data4[i] = rest >> (8 - i - 1) * 8 & 0xff

        SHGetKnownFolderPath = windll.shell32.SHGetKnownFolderPath
        SHGetKnownFolderPath.argtypes = [
            ctypes.POINTER(GUID), wintypes.DWORD,
            wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)
        ]
        FOLDERID_Download = '{374DE290-123F-4565-9164-39C4925E467B}'

        pathptr = ctypes.c_wchar_p()
        guid = GUID(FOLDERID_Download)
        if SHGetKnownFolderPath(ctypes.byref(guid), 0, 0, ctypes.byref(pathptr)):
            raise ctypes.WinError()
        return pathptr.value
    else:
        return os.path.join(os.path.expanduser("~"), "Downloads")

def download_ffmpeg(url):
    output_folder = os.path.join(current_directory, "ffmpeg")
    # Make sure the output folder exists, create it if not
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # Fetch the ffmpeg zip file from the given URL
    response = requests.get(url)
    zip_file_path = os.path.join(output_folder, "ffmpeg.zip")

    # Save the zip file to the output folder
    with open(zip_file_path, "wb") as zip_file:
        zip_file.write(response.content)

    # Extract the contents of the zip file
    with ZipFile(zip_file_path, "r") as zip_ref:
        zip_ref.extractall(output_folder)

    # Remove the zip file once extraction is done
    os.remove(zip_file_path)

def find_or_create_ffmpeg_path():
    local_ffmpeg_path = os.path.join(current_directory, 'ffmpeg/ffmpeg-master-latest-win64-gpl/bin/ffmpeg.exe')
    if os.path.exists(local_ffmpeg_path):
        return local_ffmpeg_path
    if os.name == 'posix':
        try:
            # Run the 'which' command to check if ffmpeg is available in the system's PATH
            result = subprocess.run(["which", "ffmpeg"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return result.stdout.decode("utf-8").strip()
        except subprocess.CalledProcessError as e:
            # If ffmpeg is not found (returns a non-zero exit code), the CalledProcessError will be raised
            print("Ffmpeg not found. If using Linux, download it first and try again. This application is untested on MacOs.")
            print(e.output)
            exit()
    elif os.name == 'nt':
        print("Ffmpeg not found. Now downloading...")
        download_link = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        download_ffmpeg(download_link)

def download_audio(urls, mp4, downloads_path):
    if mp4:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'postprocessors': [
                {
                    'key': 'FFmpegVideoRemuxer',
                    'preferedformat': 'mp4',
                }
            ],
            'outtmpl': f'{downloads_path}/%(title)s.%(ext)s',
            'ffmpeg_location': os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'ffmpeg'),
        }
    else:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': False,
            'outtmpl': f'{downloads_path}/%(title)s.%(ext)s',
            'ffmpeg_location': find_or_create_ffmpeg_path(),
        }

    file_paths = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(urls)
        #get file paths
        for url in urls:
            info_dict = ydl.extract_info(url, download=False)
            file_path = ydl.prepare_filename(info_dict)
            if file_path.endswith(".webm"):
                file_path = file_path.removesuffix(".webm")
                if mp4:
                    file_path = file_path + ".mp4"
                else:
                    file_path = file_path + ".mp3"
            file_paths.append(file_path)
    return file_paths

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='ytMp3dl')
    parser.add_argument('urls', nargs='*', help = 'The list of urls to download')
    parser.add_argument('-v', '--mp4', action='store_true', help='Sets filetype to mp4')
    parser.add_argument('-p', '--path', help = 'Changes download path')
    parser.add_argument('-s', '--showpath', action='store_true', help='Show the default download path')
    args = parser.parse_args()

    path = get_downloads_path()
    using_args = len(sys.argv) > 1
    if using_args:
        if args.showpath:
            print(path)
            exit()
        urls = args.urls
        mp4 = args.mp4
        if args.path is not None:
            path = args.path
    else:
        urls = re.split(r'[,\s]+', input("Enter URL(s):").strip())
        mp4 = input("Download as mp4 [y], or mp3 [n]?") == 'y'
        path_response = input(f"Download all to: {path}? [y/n]")
        if path_response == 'n':
            path = input("Enter Path:")

    file_paths = download_audio(urls, mp4, path)
    for file_path in file_paths:
        try:
            os.utime(file_path)
        except:
            print("Could not fix modified time of " + file_path)
