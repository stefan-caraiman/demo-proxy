import os

from flask import Flask,redirect

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hey, we have Flask in a Docker container!'

@app.route('/example-proxy')
def proxied_content():
    return redirect("http://www.example.com", code=302)


if __name == '__main__':
    port = int(os.environ.get('PORT', 80))
    app.run(host='0.0.0.0', port=port)
