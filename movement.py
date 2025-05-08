import time
import threading
import pigpio
import RPi.GPIO as GPIO
import requests
from picamera2 import Picamera2
import cv2
from gtts import gTTS
import playsound
import os
import face_recognition as fr
import speech_recognition as sr

# === GPIO Pin Definitions ===
IN1 = 27
IN2 = 22
SERVO_DIR = 13
SERVO_HEAD = 12

TRIG = {'S1': 16, 'S2': 8, 'S3': 6, 'S4': 17}  #Only the first sensor is used lol
ECHO = {'S1': 7, 'S2': 24, 'S3': 26, 'S4': 23}

THRESHOLD = 90  # Distance threshold
SERVO2_ANGLES = {'UP': 125, 'DOWN': 90}

# FastAPI endpoint for chatbot
FASTAPI_URL = "<YOUR IP:PORT>"  # Replace with your server's IP and port

# Send user prompt to chatbot server

def send_message_to_server(prompt):
    #This could be a bit modified to give shorter responses as shorter responses means faster processing of ans
    formal_prompt = f"Please respond to the following question briefly and formally: {prompt}"

    # json payload
    payload = {
        "prompt": formal_prompt
    }

    try:
        print(f"Sending request to server: {FASTAPI_URL}")
        response = requests.post(FASTAPI_URL, json=payload)
        print(f"Response Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                #this part has additional bits for debugging purposes you can remove this if you want
                # Log the full response content
                print("Full Response Content:", response.text) 
                
                # Parse the JSON response
                response_data = response.json()
                print("Parsed Response Data:", response_data)

                # get 'role' and 'content' in the response
                if 'role' in response_data and 'content' in response_data:
                    print(f"{response_data['role']}: {response_data['content']}")
                    speak(response_data['content'])  # Speak the response content
                else:
                    print("Error: 'role' or 'content' key not found in the response.")
            except ValueError:
                print("Error: Response is not a valid JSON.")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")

def speak(text):
    #for this i save the TTS audio file instead of reading the TTS line by line tried that with another project didnt work properly so this is being used for now
    print("Speaking...")
    tts = gTTS(text=text, lang='en')
    tts.save("response.mp3")
    playsound.playsound("response.mp3")
    os.remove("response.mp3")

# GPIO setup
# this should probably be up but whatever i was too lazy to change it 
gpio = GPIO
pio = pigpio.pi()
gpio.setmode(gpio.BCM)
    
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)}))
picam2.start()

gpio.setup(IN1, gpio.OUT)
gpio.setup(IN2, gpio.OUT)
for sensor in TRIG:
    gpio.setup(TRIG[sensor], gpio.OUT)
    gpio.setup(ECHO[sensor], gpio.IN)

# Center steering servo at startup
duty = int(500 + (92 / 180.0) * 2000)  # Center angle
pio.set_servo_pulsewidth(SERVO_DIR, duty)
time.sleep(0.5)

#face recognition stuff
face_match = False
matched_name = "Unknown"

person_image = fr.load_image_file("img1.jpg")
person_face_encoding = fr.face_encodings(person_image)[0] #Inorder to save other faces we need to use access the image through load_image_file and then get the encodings of the image
#the  format is same for all the other faces

known_face_encodings = [person_face_encoding] # store their encodings in a list also you have to store them in the same order as the names other wise it will be a mess
known_face_names = ["NAME OF THE PERSON"] # add the name of the person in the same order as the encodings

face_locations = []
face_encodings = []
counter = 0 #this is used to run the face recognition  every 30 frames

def recognize_speech_from_mic():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold = 2

    try:
        with sr.Microphone() as source:
            print("Calibrating microphone... Please wait.")
            recognizer.adjust_for_ambient_noise(source, duration=3) # probably need to remove this because it does take a bit time to initiate the microphone
            print("Listening for up to 4 seconds...")
            audio = recognizer.listen(source, timeout=4)

        print("Recognizing...")
        return recognizer.recognize_google(audio, language="en-in")

    except sr.UnknownValueError:
        print("Sorry, I couldn't understand the audio.")
        return ""
    except sr.RequestError as e:
        print(f"Could not connect to Google's Speech Recognition service: {e}")
        return ""
    except Exception as ex:
        print(f"Unexpected error: {ex}")
        return ""

def recog_face(encodings):
    global face_match
    global matched_name
    global known_face_encodings
    global face_encodings
    global face_locations # i dont think face_locations is needed but whatever i stole this from my other project so i am using it

    face_match = False
    matched_name = "Unknown"

    try:
        matches = fr.compare_faces(known_face_encodings, encodings[0])
        if True in matches and encodings[0] is not None:
            matched_index = matches.index(True)
            matched_name = known_face_names[matched_index]
            face_match = True
        else:
            face_match = False
            matched_name = "unknown"
    except ValueError:
        pass

# Motor control functions
def move_forward():
    gpio.output(IN1, gpio.HIGH)
    gpio.output(IN2, gpio.LOW)
    print("Moving forward...")

def move_backward():
    gpio.output(IN1, gpio.LOW)
    gpio.output(IN2, gpio.HIGH)
    print("Moving backward...")

def stop_motors():
    gpio.output(IN1, gpio.LOW)
    gpio.output(IN2, gpio.LOW)
    print("Motors stopped.")

# Head control functions
def head_up(pi_obj, pin, start, end, face_detected_fn, delay=0.2):
    print("[HEAD] Scanning upward...")
    for angle in range(start, end + 1):
        if face_detected_fn():  
            print("[HEAD] Face detected — stopping head movement.")
            break
        duty = int(500 + (angle / 180.0) * 2000)
        pi_obj.set_servo_pulsewidth(pin, duty)
        time.sleep(delay)

    #pi_obj.set_servo_pulsewidth(pin, 0) # dont use this 

def head_down(pi_obj, pin, start, end, delay=0.02):
    print("[HEAD] Moving down...")
    for angle in range(start, end - 1, -1):
        duty = int(500 + (angle / 180.0) * 2000)
        pi_obj.set_servo_pulsewidth(pin, duty)
        time.sleep(delay)
    pi_obj.set_servo_pulsewidth(pin, 0)  # Stop servo pulse
    print("[HEAD] Head moved down.")

def face_detected(): # this is detected when face is inside a threshold
    return face_distance is not None and face_distance < 120

# Ultrasonic sensor read
def read_distance(sensor):
    trig = TRIG[sensor]
    echo = ECHO[sensor]
    gpio.output(trig, False)
    time.sleep(0.05)
    gpio.output(trig, True)
    time.sleep(0.00001)
    gpio.output(trig, False)
    start = time.time()
    timeout = start + 0.1
    while gpio.input(echo) == 0 and time.time() < timeout:
        pulse_start = time.time()
    while gpio.input(echo) == 1 and time.time() < timeout:
        pulse_end = time.time()
    if 'pulse_start' not in locals() or 'pulse_end' not in locals():
        return 999
    dist = (pulse_end - pulse_start) * 17150
    return round(dist, 2)

# Camera thread to update face_distance
face_distance = None
def camera_thread():
    global face_distance, counter, face_match, matched_name, face_locations, face_encodings

    focal = 615
    realW = 14.0
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

    while True:
        frame = picam2.capture_array()

        # Rotate and convert to grayscale
        frame = cv2.rotate(frame, cv2.ROTATE_180)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) #grayscale is not being used in the face recognition part but it is used in the face detection part

        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))

        # Run face recognition every 30 frames
        if counter % 30 == 0:
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            face_locations = fr.face_locations(frame_bgr)
            face_encodings = fr.face_encodings(frame_bgr, face_locations)
            if face_encodings:
                try:
                    threading.Thread(target=recog_face, args=(face_encodings,)).start() #this is kinda weird as thread within a thread sounds like a bomb to me but whatever
                except ValueError:
                    pass
            else:
                face_match = False

        counter += 1

        if face_match:
            cv2.putText(frame, f"MATCH! {matched_name}", (20, 450), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)
        else:
            cv2.putText(frame, "NO MATCH!", (20, 450), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)

        if len(faces):
            x, y, w, h = faces[0]
            face_distance = (realW * focal) / w
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        else:
            face_distance = None

        cv2.imshow("Camera Feed", frame)
        cv2.waitKey(1)
        time.sleep(0.05)

# Start camera thread
threading.Thread(target=camera_thread, daemon=True).start() #the camera runs outside of the main loop

#not really autonomous stuff but i had a short amount of time to do this so i just did this 
def recover_and_move():
    print("Obstacle detected. Executing recovery maneuver...")

    # Turn steering servo to RIGHT
    target_angle = 54  # Turn wheels to the right
    duty = int(500 + (target_angle / 180.0) * 2000)
    pio.set_servo_pulsewidth(SERVO_DIR, duty)
    print("Turning wheels right...")
    time.sleep(1)

    # Move backward while steering right
    move_backward()
    print("Reversing with turn...")
    time.sleep(2)
    stop_motors()

    target_angle = 130  # Turn wheels to the left
    duty = int(500 + (target_angle / 180.0) * 2000)
    pio.set_servo_pulsewidth(SERVO_DIR, duty)
    print("Turning wheels left...")
    time.sleep(1)

    # Move forward after maneuver
    move_forward()
    print("Moving forward...")
    time.sleep(3)  # Move forward for 6.5 seconds
    stop_motors()

    # Center the steering
    target_angle = 92  # Center angle
    duty = int(500 + (target_angle / 180.0) * 2000)
    pio.set_servo_pulsewidth(SERVO_DIR, duty)
    print("Centering steering...")
    time.sleep(1)

    # Add a step to continue moving forward after centering
    move_forward()  # This will start moving forward again after the recovery
    print("Resuming forward movement...")

#this is where the main loop starts
try:
    last_greet_time = 0  # Cooldown to prevent spamming greetings

    while True:
        dist = read_distance('S1')

        if dist < THRESHOLD:
            stop_motors()
            print("Obstacle detected. Raising head...")

            head_up(pio, SERVO_HEAD, SERVO2_ANGLES['DOWN'], SERVO2_ANGLES['UP'], face_detected) 

            # Allow some time for camera_thread to update face_distance and matched_name
            time.sleep(0.5)

            if face_distance is not None and face_distance < 300:
                print(f"[CAMERA] Face detected at {face_distance:.2f} cm.")

                if time.time() - last_greet_time > 30:  # Greet cooldown
                    last_greet_time = time.time()

                    if face_match: #this doesnt really work as the time taken to lift the head and recognize the face is too long and since it gives false it will always detect the person as a stranger but it does work sometimes
                        #This part can be modified if we do give a timer to wait for the face to be recognized but its creates a delay so i just left it as it is
                        print(f"Robot: Hello {matched_name}!")
                        send_message_to_server(f"Say a warm and short greeting to {matched_name}.")
                    else:
                        print("Robot: Hello!")
                        send_message_to_server("Say a friendly hello to a stranger.")

                print("Initiating voice conversation...")

                while True:
                    recognized_text = recognize_speech_from_mic()
                    if not recognized_text:
                        print("No speech detected.")
                        continue

                    send_message_to_server(recognized_text)

                    if recognized_text.lower() in ['goodbye', 'bye', 'exit', 'quit', 'thankyou']:
                        print("Robot: Goodbye!")
                        head_down(pio, SERVO_HEAD, SERVO2_ANGLES['UP'], SERVO2_ANGLES['DOWN'])
                        break

                recover_and_move()

            else:
                print("No close face detected. Performing recovery...")
                head_down(pio, SERVO_HEAD, SERVO2_ANGLES['UP'], SERVO2_ANGLES['DOWN'])
                recover_and_move()

        else:
            move_forward()
            time.sleep(0.1)

except KeyboardInterrupt:
    stop_motors()
    gpio.cleanup()
    pio.stop()
    cv2.destroyAllWindows()