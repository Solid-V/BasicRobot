# RobotForSeniors
Programmed a robot for the seniors that moves, recognises you, and talks as well
The movement script runs on a raspberry pi 4B model with 8gb of ram (this board is a bit slow but it gets the job done and you need a fast SD card to flash your os it uses the raspbian bookworm os for 64 bit systems)

This project can be used to learn how gpio signals are sent and how the logic for robots can be written also it uses opencv and face_recognition library for live face detection and recognition plus used threading with recognition running each 30 frames to improve the speed of the camera feed, it also uses the ollama python module to communicate with the hosted server on another device note that both the raspberry pi with the movement script and the computer which will host the server should be connected to the same network
