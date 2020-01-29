from flask import Flask  # Import the Flask class
app = Flask(__name__)    # Create an instance of the class for our use

app.config["DEBUG"] = True
app.config["JSON_SORT_KEYS"] = False
CORS(app)