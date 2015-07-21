# -*- coding: utf-8 -*-
import os
import struct
import json
import socket
import ssl
import select
import time
from threading import Thread


class APNs(object):
    def __init__(self, **kwarg):
        self.payload = None
        self.clear_payload = False
        self.lock_send = False
        self.exit_feedback = False
        apns_time_out = kwarg.get('apns_time_out')
        self.apns_time_out = 3 if apns_time_out is None else int(apns_time_out)
        self.epoll = select.epoll()
        self.host = "gateway.sandbox.push.apple.com"
        self.port = 2195
        self.cert_file = kwarg.get('cert_file')
        if kwarg.get('debug') is False:
            self.host = "feedback.push.apple.com"

        if os.path.isfile(self.cert_file):
            self.open()
            self.start_feedback()

    def start_feedback(self):
        self._feedback_thread = Thread(target=self._feedback, args=(self,))
        self._feedback_thread.start()
        print "DEBUG: start feedback %s" % self._feedback_thread.getName()

    def open(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
        except socket.gaierror:
            print "ERROR: can't connect"
            self.reset()
        self.connect = ssl.wrap_socket(self.socket, certfile=self.cert_file)
        self.epoll.register(self.connect.fileno(), select.EPOLLIN | select.EPOLLET)

    def close(self):
        if hasattr(self, "epoll") and not self.epoll is None:
            self.epoll.unregister(self.connect.fileno())
        self.connect.close()
        self.socket.close()

    def send(self, payload=None):
        if self.lock_send is True:
            print "DEBUG: send is lock"
            return False
        if not payload is None:
            self.payload = payload
        if self.payload is None:
            return None
        data = self.payload.get_frames()
        if data:
            try:
                self.connect.sendall(data)
            except socket.error:
                print "ERROR: feil send, reset"
                self.reset()
                return None
            self.clear_payload = True
        else:
            return None

    def _feedback(*arg, **kwarg):
        self = arg[0]

        while self.exit_feedback is False:
            if self.epoll is None:
                continue

            events = self.epoll.poll(3 if self.apns_time_out is None else self.apns_time_out)

            if events == []:
                if not self.payload is None and self.payload.frames != [] and self.clear_payload is True:
                    print "DEBUG: clear quere"
                    self.payload.clear()
                    self.clear_payload = False
                continue

            for fileno, event in events:
                if fileno != self.connect.fileno():
                    continue

                if event == select.EPOLLIN:
                    self.clear_payload = False
                    respons = self.connect.read()
                    # unpack invalid id
                    print "DEBUG: feedback message: %s" % respons.encode('hex')
                    invalid_id = struct.unpack('>I', respons[2:6])[0]
                    self.payload.clear_invalid_id(invalid_id)
                    self.reset()  # Wag the Dog
                elif event == 25:
                    print "DEBUG: event 25, reset"
                    self.reset()  # Wag the Dog
                else:
                    print "DEBUG: other event", event

        print "DEBUG: stop feedback %s" % self._feedback_thread.getName()

    def reset(self):
        self.close()
        time.sleep(3)  # os relax
        self.open()
        if not self.payload is None and self.payload.frames != []:
            self.send()


class Payload(object):
    def __init__(self, **kwarg):
        self.ids = {}
        self.frames = []

    def clear(self):
        self.__init__()

    def add_frame(self, **kwarg):
        if kwarg == {}:
            return None

        token = kwarg.get('token')
        text = kwarg.get('text')

        if token is None or \
           text is None:
            return False

        if len(token.decode('hex')) != 32:
            print "Error: token size != 32"
            return False

        identifier = 0 if self.ids == {} else max(self.ids.keys()) + 1
        if identifier > (1 << 32) - 1:
            print "Error: max identifier"
            return False

        frame = {"token": token,
                 "identifier": identifier,
                 "data":
                 {"aps":
                  {"sound": "default",
                   "badge": 1,
                   "alert": text
                   }
                  }
                 }

        sound = kwarg.get("sound")
        if not sound is None:
            frame["data"]["aps"]["sound"] = sound

        badge = kwarg.get("icon")
        if not badge is None:
            frame["data"]["aps"]["badge"] = badge

        if len(json.dumps(frame["data"], separators=(',', ':'), ensure_ascii=False)) > 256:
            print "Error: alert size > 256"
            return False

        expiry = kwarg.get('expiry')
        if not expiry is None:
            frame["expiry"] = expiry

        priority = kwarg.get('priority')
        if not priority is False:
            frame["priority"] = priority

        self.ids[identifier] = {'token': token, 'place': len(self.frames)}
        self.frames.append(frame)
        return True

    def get_frames(self):
        frames = ''
        for x in self.frames:
            frame = self.get_frame(x)
            frames += frame
        return frames

    @classmethod
    def get_frame(self, x=None):
        if x is None:
            return False
        frame = ''
        # token item
        token_bin = x["token"].decode('hex')
        token_length_bin = struct.pack('>H', (len(token_bin)))

        frame += '\x01'
        frame += token_length_bin
        frame += token_bin

        # payload item
        data = x["data"]

        payload_json = json.dumps(data, separators=(',', ':'), ensure_ascii=False)
        payload_length_bin = struct.pack('>H', (len(payload_json)))

        frame += '\x02'
        frame += payload_length_bin
        frame += payload_json

        # identifier item
        identifier_bin = struct.pack('>I', x["identifier"])
        identifier_length_bin = struct.pack('>H', len(identifier_bin))

        frame += '\x03'
        frame += identifier_length_bin
        frame += identifier_bin

        # expiry item
        expiry = x.get('expiry')
        if not expiry is None:
            expiry_bin = struct.pack('>I', expiry)
            expiry_length_bin = struct.pack('>H', len(expiry_bin))

            frame += '\x04'
            frame += expiry_length_bin
            frame += expiry_bin

        # priority item
        priority = x.get('priority')
        if not priority is None:
            priority_bin = chr(priority)
            priority_length_bin = struct.pack('>H', len(priority_bin))

            frame += '\x05'
            frame += priority_length_bin
            frame += priority_bin

        # frame len
        frame_len_bin = struct.pack('>I', len(frame))
        frame = '\x02' + frame_len_bin + frame
        return frame

    def clear_invalid_id(self, id):
        if not id in self.ids.keys():
            return False
        bad_token = self.ids[id]['token']
        place = self.ids[id]['place']

        self.frames = self.frames[place + 1:]

        for x in self.ids.keys():
            if place >= self.ids[x]['place']:
                del self.ids[x]
            else:
                self.ids[x]['place'] -= (place + 1)

        # TODO clear bad token from db
        print "Bad token: %s" % bad_token
