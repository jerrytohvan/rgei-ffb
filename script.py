import colorgram, json
import cv2
import numpy as np
import urllib
import pyrebase
from skimage import io
from flask import jsonify

config = {
    "apiKey": "AIzaSyDR0JBAKQvqrCbvCLzxPT_fbxSplTgFSEE",
    "authDomain": "computervision-7e5fb.firebaseapp.com",
    "databaseURL": "https://computervision-7e5fb.firebaseio.com",
    "projectId": "computervision-7e5fb",
    "storageBucket": "computervision-7e5fb.appspot.com",
    "messagingSenderId": "62106225870"
  }



def background_removal(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask1 = cv2.inRange(hsv, (0, 60, 20), (10, 255,255))
    mask2 = cv2.inRange(hsv, (10,100,100), (30, 255, 255))
    mask = cv2.bitwise_or(mask1, mask2)
    target = cv2.bitwise_and(img,img, mask=mask)

    #black to transparent
    tmp = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
    _,alpha = cv2.threshold(tmp,0,255,cv2.THRESH_BINARY)
    b, g, r = cv2.split(target)
    rgba = [b,g,r, alpha]
    dst = cv2.merge(rgba,4)

    #stores in temp folder
    cv2.imwrite('temp-filtered.png', dst)
    #RGB - Blue
    cv2.imwrite('B-RGB.jpg',dst[:, :, 0])
    # RGB - Green
    cv2.imwrite('G-RGB.jpg',dst[:, :, 1])
    # RGB Red
    cv2.imwrite('R-RGB.jpg',dst[:, :, 2])

    #[saved_name, img object]
    return dst

def ripness_index(img):
    # The range of ripe values obtained
    # varies from a minimum value of 3.56 to a maximum
    # of 5.83. Whereas the highest ripeness index for the
    # unripe fruits is 2.49. It can be concluded here that the
    # threshold value of 3.5 can actually be reduced to 3.0
    # because the highest unripe value will not exceed 2.5
    # for this particular sampling batch.
    #0 = under
    #1 = ripe
    #2 = overripe
    avg_color_per_row = np.average(img, axis=0)
    avg_color = np.average(avg_color_per_row, axis=0)

    up = float(avg_color[2])
    base = float(avg_color[1]) * float(avg_color[0])
    ri = up* up / base

    ripe = False
    status_code = 0
    if ri > 3.56 and ri <5.83:
        ripe = True
        status_code = 1
    elif ri < 3.56:
        status_code =  0
    else:
        status_code =  2

    return [ri, status_code]

# def color_normalisation(color):
#     red = color.rgb.r
#     green = color.rgb.g
#     blue = color.rgb.b
#     s = red + green + blue
#     return [red/s, green/s, blue/s]

def is_ripe(color):
    #ripe
    ripe_red_range = range(127,146)
    ripe_green_range = range(81,95)
    ripe_blue_range = range(52,72)

    #unripe
    unripe_red_range = range(66,101)
    unripe_green_range = range(42,66)
    unripe_blue_range = range(28,52)

     #over
    over_red_range = range(136,155)
    over_green_range = range(83,98)
    over_blue_range = range(51,70)

    #normalisation
    red = color.rgb.r
    green = color.rgb.g
    blue = color.rgb.b

    if(red in ripe_red_range and green in ripe_green_range and blue in ripe_blue_range):
        return 1
    elif(red in unripe_red_range and green in unripe_green_range and blue in unripe_blue_range):
        return 2
    elif(red in over_red_range and green in over_green_range and blue in over_blue_range):
        return 0


def run_process():
    firebase = pyrebase.initialize_app(config)
    storage = firebase.storage()
    db = firebase.database()
    ffbs = db.child("ffbs").order_by_child("date_added").limit_to_last(2).get()
    # ffbs = db.child("ffbs").get()
    container = {}
    for ffb in ffbs.each():
        container[ffb.key()] = [ffb.val().get('date_added'),ffb.val().get('filename') ]

    #IMG download
    key = ffbs.each()[1].key()
    filename = "rge-ffb-evaluator/" +container[key][1]
    url = storage.child(filename).get_url(None)
    img = io.imread(url)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    processed_img = background_removal(img)

    # Extract 6 colors from an image using K Clustering
    colors = colorgram.extract('./temp-filtered.png', 10)
    color_banks = {}
    #get proportions, by excluding black
    black_proportion = 0
    black_exist = False
    for color in colors:
        if color.rgb.r <= 15 and color.rgb.g <= 15 and color.rgb.b <= 15:
            black_proportion = color.proportion
            black_exist = True

    ripe = False
    ripeness_status = 0
    for color in colors:
        # calibrate
        if  (color.rgb.r > 15 and color.rgb.g > 15 and color.rgb.b > 15):
            predict = is_ripe(color)
            if predict == 1:
                ripe = True
            color_banks[color.proportion/(1-black_proportion)] = [color.rgb.r, color.rgb.g, color.rgb.b]

    #if none of color indicator classified under ripe how do we measure fruit maturity (over/under?)
    color_banks["ripe"] = ripe
    color_banks["status"] = ripeness_status

    #check for ripeness index
    ri = ripness_index(processed_img)
    color_banks["ripeness_index"] = ri[0]
    color_banks["ripeness_index_status"] = ri[1]

    #Encode
    return json.JSONEncoder().encode(color_banks)

app = Flask(__name__)

@app.route('/')
def index():
    d = make_summary()
    return d
    
# print run_process()