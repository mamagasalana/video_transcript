import requests
import glob
def imgur(fpath):
    
    with open(fpath, "rb") as f:
        files = {
            "image": (fpath, f, "image/png"),
        }
        url = 'https://api.imgur.com/3/upload?client_id=d70305e7c3ac5c6'
        s =requests.Session()

        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en-US,en;q=0.9",
            "origin": "https://imgur.com",
            "priority": "u=1, i",
            "referer": "https://imgur.com/",
            "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        }
        data = {"type": "file", "name": fpath,}
        r = s.post(url, headers=headers ,  data=data, files=files)
        return r


if __name__  == '__main__':
    imgur_path=  {}
    for f in glob.glob('outputs/viz/*.png'):
        imgur_path[f] = imgur(f)