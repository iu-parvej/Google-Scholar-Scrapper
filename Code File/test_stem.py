import socket
socket.setdefaulttimeout(5)
import stem.control
try:
    with stem.control.Controller.from_port(port=9151) as controller:
        controller.authenticate()
        print("Connected!")
except Exception as e:
    print("Error:", e)
