import socket
import random
import pickle
import time
import threading
import configparser
import select
from queue import Queue

server_address = ('localhost', 7777)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# queue for requests
packet_queue = Queue(maxsize = 0) # 0 = infinite size

# Que for client keyboard input
input_que = Queue(maxsize=10)


# ------ CORE PROCESSES ------------


def extract_header(data):
    headerR = [0]
    for x in data:
        if x == "!":
            for z in data:
                if z == "?":
                    break
                else:
                    if z != "!":
                        headerR = z
        return headerR


def extract_payload(data):
    nekst = 0
    payload = None

    for z in data:
        if nekst == 1:
            payload = z
            break
        if z == "?":
            nekst = 1
    return payload


def set_flags(sek, ack, syn, fin):
    our_head = [0, 0, 0, 0]
    our_head[0] = sek
    our_head[1] = ack
    our_head[2] = syn
    our_head[3] = fin
    return our_head

# --- Classes that spawn threads
# ----------------- RESPONSE HANDLER --------------------


class ResponseHandler(threading.Thread):  # Distributor
    def __init__(self, address, packet):
        threading.Thread.__init__(self)
        self.address = address
        self.packet = packet

    def run(self):
        handle_response(self.address, self.packet)


def handle_response(this_address, packet):
    sent = sock.sendto(packet, this_address)


# --------- REQUEST HANDLERS -----------------------------


class RequestHandler(threading.Thread):  # Request Handler
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        handle_requests()

def handle_requests():
    while True:
        data, address = sock.recvfrom(4096)
        data_arr = pickle.loads(data)
        print('received "%s"' % repr(data_arr))

        # Put in queue
        packet_queue.put([server_address, data_arr])


# --------- DISTRIBUTOR FOR NON ACK CLIENTS-----------------------------


class Distributor(threading.Thread):  # Distributor
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        distribute()


def distribute():
    global server_address
    process_list = [] # address, process_code
    process_code = initConnection()  # init three way handshake
    response_handler_thread = ResponseHandler(server_address, process_code[1])
    response_handler_thread.start()
    process_list.append([server_address, process_code[0]])

    time.sleep(4.5) # needs to wait until sendto has happened
    request_handler_thread = RequestHandler()
    request_handler_thread.start()

    while True:
        new = True
        if packet_queue.empty() is False:

            packet = packet_queue.get() #pop packet from que

            for i in process_list:

                if i[0] == server_address: # if ongoing process
                    new = False
                    process_code = ongoing_process(i[1], packet)

                    if process_code[0] == "syn-ack-complete":
                        i[1] = "chat-true"
                        server_address = process_code[1]
                        i[0] = server_address
                        print("TCP like connection obtained")
                        response_handler_thread = ResponseHandler(server_address, process_code[2])
                        response_handler_thread.start()
                        input_thread = KeyBoardListener()
                        input_thread.start()


                    elif process_code[0] == "bad":
                        process_list.remove(i)
                        print("removed process")
                        # should respond with generic code saying that process has been dropped

                    elif 1:  # update process_code
                        i[1] = process_code[0]
                        response_handler_thread = ResponseHandler(server_address, process_code[1])
                        response_handler_thread.start()



            if new:  # if new process
                process_code = ongoing_process("hand-0", packet)
                if process_code[0] != "bad":
                    process_list.append([server_address, process_code[0]])
                    response_handler_thread = ResponseHandler(server_address, process_code[1])
                    response_handler_thread.start()


# --------------- KEYBOARD LISTENER----------------------------


class KeyBoardListener(threading.Thread):  # Distributor
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        listen_for_input()


def listen_for_input():
    while True:
        print("listening for input..")
        inp = input()
        if input_que.full() is True:
            print("que full, wait a bit for requests to be processed")
            time.sleep(0.5)
        else:
            input_que.put(inp)


# --------------INIT FUNCTION------------------------------

def initConnection():
    our_head = [0,0,0,0]

    seqSart = random.randint(1, 1001)
    our_head[0] = seqSart
    our_head[1] = 0
    our_head[2] = 1
    our_head[3] = 0

    #now send segment with no payload to listening port
    load = "com-0"
    cucumber = ["!", our_head, "?", load]
    data_string = pickle.dumps(cucumber)
    print("sending syn to server")
    return ["hand-0", data_string]


# ------------------- PROTOCOLS --------------------------

def ongoing_process(process_info, packet):

    head = extract_header(packet[1])
    payload = extract_payload(packet[1])

    if process_info == "hand-0":
        if head[2] == 1:
            if payload == "com-0 accept":
                print("syn received ")
                our_head = set_flags(head[1], head[0] + 1, 0, 0)
                load = "com-0 accept"
                cucumber = ["!", our_head, "?", load]
                data_string = pickle.dumps(cucumber)
                print("sending ack to server")
                return ["recv_sock", data_string]

    if process_info == "recv_sock":
        print("socket received")
        load = None
        our_head = set_flags(head[1], head[0] + 1, 0, 0)
        cucumber = ["!", our_head, "?", load]
        data_string = pickle.dumps(cucumber)
        print("sending input to server")
        return ["syn-ack-complete", payload, data_string]  # payload is the new socket address

    if process_info == "chat-true":
        while input_que.empty() is True:
            time.sleep(0)
        load = input_que.get()
        our_head = set_flags(head[1], head[0] + 1, 0, 0)
        cucumber = ["!", our_head, "?", load]
        data_string = pickle.dumps(cucumber)
        print("sending input to server")
        return ["chat-true", data_string]  # payload is the new socket address

    else:
        return ["bad", None]


# --------------- MAIN --------------------

distributor_thread = Distributor()

distributor_thread.start()

