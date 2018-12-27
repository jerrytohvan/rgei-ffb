import colorgram, json
import cv2
import numpy as np
import urllib
import pyrebase
import os
import imutils
import itertools
import matplotlib.pyplot as plt
from skimage import io
from flask import jsonify
from flask import Flask, send_file

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

def get_pixels_of_reference_object(img):
    #https://www.pyimagesearch.com/2016/03/28/measuring-size-of-objects-in-an-image-with-opencv/

    #get length of reference object
    ACTUAL_CM_SIZE_LENGTH = 10.0
    ACTUAL_CM_SIZE_WIDTH = 3.0
    object_found = False

     # chroma key color boundaries (R,B and G)
    lower = [0, 200, 0]
    upper = [20, 255, 20]

    # # # create NumPy arrays from the boundaries
    lower = np.array(lower, dtype="uint8")
    upper = np.array(upper, dtype="uint8")

    # # find the colors within the specified boundaries and apply
    # # the mask
    mask = cv2.inRange(img, lower, upper)
    output = cv2.bitwise_and(img, img, mask=mask)
    
    ret,thresh = cv2.threshold(mask, 40, 255, 0)
    cv2.threshold(cv2.cvtColor(output, cv2.COLOR_BGR2GRAY),127, 255, cv2.THRESH_BINARY)
    im2,contours,hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) != 0:
        # cv2.drawContours(output, contours, -1, (255,0,0), 3)
        if len(contours) == 1:
            object_found = True

        # measure length and pixel
            minx = None
            maxx = None
            miny = None
            maxy = None

            x,y,w,h = cv2.boundingRect(contours[0])
            if minx is None:
                minx = x
            elif x < minx:
                minx = x

            if maxx is None:
                maxx = x+w 
            elif x+w > maxx:
                maxx = x+w

            if miny is None:
                miny = y
            elif y < miny:
                miny = y

            if maxy is None:
                maxy = y+h
            elif y+h > maxy:
                maxy = y+h

            cv2.rectangle(output,(x,y),(x+w,y+h),(255,0,0),2)

            #top
            cv2.circle(output, (minx+(maxx-minx)/2,miny), 8, (0, 0, 255), -1)
            #bottom
            cv2.circle(output, (minx+(maxx-minx)/2,maxy), 8, (0, 255, 0), -1)
            #right
            cv2.circle(output, (maxx,miny+((maxy-miny)/2)), 8, (0, 255, 255), -1)
            #left
            cv2.circle(output, (minx,miny+((maxy-miny)/2)), 8, (255, 255, 0), -1)

            # cm per unit
            if maxx>maxy:
                #x axis is the length
                LENGTH_PER_PIXEL = ACTUAL_CM_SIZE_LENGTH/(maxx-minx)
                WIDTH_PER_PIXEL = ACTUAL_CM_SIZE_WIDTH/(maxy-miny)
            else:
                #y axis is the length
                WIDTH_PER_PIXEL = ACTUAL_CM_SIZE_WIDTH/(maxx-minx)
                LENGTH_PER_PIXEL= ACTUAL_CM_SIZE_LENGTH/(maxy-miny)

    cv2.imwrite('chroma_object.png', output)

    #identify pixels per metric
    return [object_found, LENGTH_PER_PIXEL, WIDTH_PER_PIXEL]

def retrieve_contour_properties(img):
    OBJECT_LENGTH = 0
    OBJECT_WIDTH = 0

    reference = get_pixels_of_reference_object(img)

    # red color boundaries (R,B and G)
    lower = [1, 0, 20]
    upper = [60, 40, 200]

    # # # create NumPy arrays from the boundaries
    lower = np.array(lower, dtype="uint8")
    upper = np.array(upper, dtype="uint8")

    # # find the colors within the specified boundaries and apply
    # # the mask
    mask = cv2.inRange(img, lower, upper)
    output = cv2.bitwise_and(img, img, mask=mask)


    ret,thresh = cv2.threshold(mask, 40, 255, 0)
    cv2.threshold(cv2.cvtColor(output, cv2.COLOR_BGR2GRAY),127, 255, cv2.THRESH_BINARY)
    im2,contours,hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    minx = None
    maxx = None
    miny = None
    maxy = None

    if len(contours) != 0:
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 300: #filtering contours
                x,y,w,h = cv2.boundingRect(cnt)
                if minx is None:
                    minx = x
                elif x < minx:
                    minx = x

                if maxx is None:
                    maxx = x+w 
                elif x+w > maxx:
                    maxx = x+w

                if miny is None:
                    miny = y
                elif y < miny:
                    miny = y

                if maxy is None:
                    maxy = y+h
                elif y+h > maxy:
                    maxy = y+h

                cv2.rectangle(output,(x,y),(x+w,y+h),(255,0,0),2)

        # include bigger contours instead
        outer_bound= cv2.rectangle(output,(minx,miny),(maxx,maxy),(0,255,0),2)

        #top
        cv2.circle(output, (minx+(maxx-minx)/2,miny), 8, (0, 0, 255), -1)
        #bottom
        cv2.circle(output, (minx+(maxx-minx)/2,maxy), 8, (0, 255, 0), -1)
        #right
        cv2.circle(output, (maxx,miny+((maxy-miny)/2)), 8, (0, 255, 255), -1)
        #left
        cv2.circle(output, (minx,miny+((maxy-miny)/2)), 8, (255, 255, 0), -1)

        
        #compare with reference object
        if(reference[0] == True):
            #define unit ratios
            reference_len = reference[1]
            reference_width = reference[2]

            #check len & width size of object
            if maxx>maxy:
                #x axis is length of object
                OBJECT_LENGTH = (maxx-minx)*reference_len
                OBJECT_WIDTH = (maxy-miny)*reference_width
            else:
                #y axis is length of object
                OBJECT_WIDTH = (maxx-minx)*reference_len
                OBJECT_LENGTH = (maxy-miny)*reference_width

    # show the images
    cv2.imwrite('contour.png', output)

    return [reference[0] , OBJECT_LENGTH, OBJECT_WIDTH]

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
        if color.rgb.r < 15 and color.rgb.g < 15 and color.rgb.b < 15:
            black_proportion = color.proportion
            black_exist = True

    ripe = False
    ripeness_status = 0
    for color in colors:
        if not (color.rgb.r < 15 and color.rgb.g < 15 and color.rgb.b < 15):
            predict = is_ripe(color)
            if predict == 1:
                ripe = True
            color_banks[color.proportion/(1-black_proportion)] = ([color.rgb.r, color.rgb.g, color.rgb.b])

    #if none of color indicator classified under ripe how do we measure fruit maturity (over/under?)
    color_banks["ripe"] = ripe
    color_banks["status"] = ripeness_status

    #check for ripeness index
    ri = ripness_index(processed_img)
    color_banks["ripeness_index"] = ri[0]
    color_banks["ripeness_index_status"] = ri[1]


    #retrieve image properties
    contour = retrieve_contour_properties(img)

    color_banks["reference_object_exists"] = contour[0]
    color_banks["object_length"] = contour[1]
    color_banks["object_width"] = contour[2]


    #identify validity of size
    if contour[1] >= 35 and contour[1] <= 45:
        color_banks["size_valid"] = 1
    else:
        color_banks["size_valid"] = 0

    return color_banks

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if __name__ == ' __main__':
    #app.debug = True
    app.run()

@app.route('/')
def index():
    d = run_process()
    return json.dumps(d, indent=4)

@app.route('/<path:path>')
def get_image(path):
    return send_file(path, mimetype='image/png')



