# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

#
# Proof of concept made for HackingHealth Montreal 2014
#   hackinghealth.ca/events/montreal/hhmtl2014/
#
    
from BaseHTTPServer import HTTPServer
from BaseHTTPServer import BaseHTTPRequestHandler

import json
import urllib
from firebase import firebase
from twilio.rest import TwilioRestClient


TWILIO_SID = "<TWILIO ACCOUNT SID>"
TWIOLO_TOKEN = "<TWILIO AUTH TOKEN>"
TWILIO_PHONE = "<TWILIO PHONENO>"
client = TwilioRestClient(TWILIO_SID, TWIOLO_TOKEN)

# JSON file backend for tests
JSON_FILENAME = "patients.json"
f = firebase.FirebaseApplication("<FIREBASE URI>", None)

YesAnswers = ["yes", "oui", "y"]
NoAnswers = ["no", "non", "n"]

def getPatientByPhone(phone):
    data = f.get("/appointment", None)
    for id, patient in data.iteritems():
        if "phone" in patient and patient["phone"] == phone:
            return id, patient
    
    return None, None

def argToArray(arguments):
    array = {}
    data = urllib.unquote(arguments)
    for l in data.split('&'):
        key = l.split('=')[0]
        val = l.split('=')[1]
        array[key] = val
    
    return array
    
def updateJsonFile(number, response):
    data = None
    needsUpdate = False
    
    print number, "said", response
    
    with open(JSON_FILENAME, "r") as fh:
        data = json.loads(fh.read())

    for patient in data["patients"]:
        if patient["phone"] == number:
            needsUpdate = True
            
            if response.lower() in YesAnswers:
                patient["status"] = "Confirmed"
            elif response.lower() in NoAnswers:
                patient["status"] = "Declined"
            else:
                patient["status"] = response

    if needsUpdate:
        with open(JSON_FILENAME, 'w') as fh:
            fh.write(json.dumps(data, sort_keys=True, indent=4))


def updateFirebase(number, response):
    data = f.get("/appointment", None)
    
    for id, patient in data.iteritems():
        if "phone" in patient and patient["phone"] == number:
            if response.lower() in YesAnswers:
                status = "confirmed"
            elif response.lower() in NoAnswers:
                status = "declined"
            else:
                status = "not-confirmed"
            
            resp = f.patch("/appointment/%s" % id, {"status": status})
            
            if "status" in resp and resp["status"] == status:
                print "Update successful for %s" % patient["lastName"]
            else:
                print resp
                

class ClinicationUpdateServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        HTTPServer.__init__(self, *args, **kwargs)

    def serve_forever(self, poll_interval=0.5):
        HTTPServer.serve_forever(self, poll_interval)


# http handler => /ask => GET, /confirm => POST 
class HttpHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/xml')
        self.end_headers()
        self.wfile.write("<Response>")
        
        if self.path.startswith("/confirm"):
            length = self.headers.getheader('Content-Length')
            if not length:
                print "No data"
                return 
            data = self.rfile.read(int(length))
            response = argToArray(data)
            
            if "From" in response and "Body" in response:
                updateFirebase(response["From"], response["Body"])
            
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        
        if not self.path.startswith("/ask?"):
            print "Invalid request at", self.path
            self.wfile.write("Invalid GET request: %s" % (self.path))
            return

        phone = self.path[11:]
        id, patient = getPatientByPhone(phone)
        
        if id and patient:
            __body = "Hi %s! This is %s. Do you confirm your appointment? Please reply Yes or No. HHMTL2014" % (patient["firstName"], patient["hospital"])
            
            message = client.sms.messages.create(body=__body, from_=TWILIO_PHONE, to=phone)
            print "Sent SMS message %s to %s" % (message.sid, patient["lastName"])
            self.wfile.write("Sent SMS message %s to %s" % (message.sid, patient["lastName"]))
            
if __name__ == "__main__":
    try:
        server = ClinicationUpdateServer(('0.0.0.0', 8080), HttpHandler)
        server.serve_forever()

    except KeyboardInterrupt:
        server.socket.close()

