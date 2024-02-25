#import statements
from flask import Flask, render_template,request,Response,redirect,session,make_response,flash
import datetime, time
import os, sys
import numpy as np
from threading import Thread
from tensorflow import keras
import tensorflow as tf
import cv2
import math
from cvzone.HandTrackingModule import HandDetector
from cvzone.ClassificationModule import Classifier
import pyodbc
from flask_mail import Mail,Message 
from random import randint
from PIL import Image
  


app = Flask(__name__, template_folder='./templates')
app.secret_key=os.urandom(24)

mail=Mail(app)

app.config["MAIL_SERVER"]='smtp.gmail.com'
app.config["MAIL_PORT"]=465
app.config["MAIL_USERNAME"]='Your mail'
app.config['MAIL_PASSWORD']='Your mail app password'                   
app.config['MAIL_USE_TLS']=False
app.config['MAIL_USE_SSL']=True

mail=Mail(app)
otp=randint(000000,999999)

conn=pyodbc.connect("DRIVER={SQL Server};SERVER=DESKTOP-AID6U93\SQLEXPRESS;DATABASE=user_reg")
cursor=conn.cursor()

#objects initiated here
camera=cv2.VideoCapture(0)
detector=HandDetector(maxHands=1)
classifier=Classifier("mod/my_model.h5","mod/labelsCopy.txt")

#some declarations
labels=["A","B","C","D","E","F","G","H","I"]
offset=20
imgSize=300

global switch
switch=1
recognized_string = ''

def gen_frames(): 
    global recognized_string # generate frame by frame from camera
    while True:
         time.sleep(2)
         success,img=camera.read()
         imgOutput=img.copy()
         hands,img=detector.findHands(img)
         if hands:
            hand=hands[0]
            x,y,w,h=hand['bbox']

            imgWhite=np.ones((imgSize,imgSize,3),np.uint8)*255
            imgCrop=img[y-offset:y + h+offset, x-offset:x + w+offset]

            imgCropShape=imgCrop.shape

            aspectRatio=h/w
            if aspectRatio > 1:
               k=imgSize/h
               wCal=math.ceil(k*w)
               imgResize=cv2.resize(imgCrop,(wCal,imgSize))
               imageResizeShape=imgResize.shape
               wGap=math.ceil((imgSize-wCal)/2)
               imgWhite[:,wGap:wCal+wGap]=imgResize
               prediction, index=classifier.getPrediction(imgWhite)
               
            else:
               k=imgSize/w
               hCal=math.ceil(k*h)
               imgResize=cv2.resize(imgCrop,(imgSize,hCal))
               imageResizeShape=imgResize.shape
               hGap=math.ceil((imgSize-hCal)/2)
               imgWhite[hGap:hCal+hGap,:]=imgResize
               prediction, index=classifier.getPrediction(imgWhite)
            
            #this is to show the output on image frame
            cv2.putText(imgOutput,labels[index],(x,y),cv2.FONT_HERSHEY_COMPLEX,2,(0,0,0),2)
            predicted_letter = labels[index]
            if predicted_letter == '':
                recognized_string += '  '
            else:
                recognized_string += predicted_letter



         try:
             ret, buffer = cv2.imencode('.jpg', imgOutput)
             imgOutput = buffer.tobytes()
             yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + imgOutput + b'\r\n') 
         except Exception as e:
                pass

#routes are defined here  

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/index')
def index():
    global recognized_string 
    if 'user_id' in session:
        return render_template('index.html',recognized_strings=recognized_string)
    else:
        return redirect('/')

@app.route('/home')
def home():
    if 'user_id' in session:
        return render_template('home.html')
    else:
        return redirect('/')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/clear', methods=['POST'])
def clear_recognized_string():
    global recognized_string
    recognized_string = ''
    return redirect('/index')

@app.route('/requests',methods=['POST','GET'])
def tasks():
    global switch,camera
    if request.method == 'POST':

        if  request.form.get('stop') == 'Stop/Start':
            
            if(switch==1):
                switch=0
                camera.release()
                cv2.destroyAllWindows()
                
            else:
                camera = cv2.VideoCapture(0)
                switch=1
    elif request.method=='GET':

        
        return redirect('/index')
    return redirect('/index')


@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/login_validation',methods=['POST'])
def login_validation():
    email=request.form.get('email')
    password=request.form.get('password')

    cursor.execute("select * from user_reg where email='{}' and password='{}'"
    .format(email,password))
    users=cursor.fetchall()

    if len(users)>0:
        session['user_id']=users[0][0]
        return redirect('/home')
    else:
        flash("Incorrect Username or Password")
        return redirect('/')

@app.route('/add_user',methods=['POST'])
def add_users():
    name=request.form.get('uname')
    email=request.form.get('uemail')
    password=request.form.get('upassword')

    cursor.execute("select * from user_reg where email='{}'"
    .format(email))
    users=cursor.fetchall()

    if len(users)==0:
        cursor.execute("""INSERT INTO user_reg(user_id,name,email,password) VALUES(NULL,'{}','{}','{}')""".format(name,email,password))
        conn.commit()

        cursor.execute("select * from user_reg where email='{}'"
        .format(email))
        myuser=cursor.fetchall()

    
        session['user_id']=myuser[0][0]
        return redirect('/home')

    else:
        flash("User already existed, please login or contact admin","danger")
        return redirect('/register')
        
@app.route('/forgetpassword')
def forgetpassword():
    return render_template('forgetpassword.html')

@app.route('/logout')
def logout():
    if len(session)!=0:
        session.pop('user_id')
    return redirect('/')

@app.route('/verify',methods=["POST"])
def verify():
    email=request.form['uemail']
    res=make_response(render_template('verify.html'))
    res.set_cookie('email',email)
    cursor.execute("select * from user_reg where email='{}'"
    .format(email))
    users=cursor.fetchall()
    if len(users)>0:
         msg=Message(subject='OTP',sender='dhanashrimhatre07@gmail.com',recipients=[email])
         msg.body=str(otp)
         mail.send(msg)
         
         return res
    flash("The user does not exist")
    return redirect('/forgetpassword')


@app.route('/changepassword')
def changepassword():
    return render_template('changepassword.html')

@app.route('/validate',methods=['POST'])
def validate():
    user_otp=request.form['otp']
    if otp==int(user_otp):
        return redirect('/changepassword')
    flash("OTP does not match")
    return redirect('/forgetpassword')


@app.route('/reset',methods=['GET','POST'])
def reset():
    uemail=request.cookies.get('email')
    password=request.form.get('pass')

    cursor.execute("""UPDATE user_reg SET password='{}' where email='{}'""".format(password,uemail))
    conn.commit()

    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
camera.release()
cv2.destroyAllWindows() 


