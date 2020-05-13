import socket
import random
import pickle
import time
import threading
import configparser
import select
from queue import Queue


# create socket and bind address to socket
server_address = ('localhost', 7777)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(server_address)

# global list of client ID's(adrress + port)
addresses = []

# queue for clients that wants connection
packet_queue_non_ack = Queue(maxsize=0)  # 0 = infinite size

# queue for connected clients
packet_queue_ack = Queue(maxsize=0)



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

# ----------------------- TIME FUNCTION ----------------------------










# --------- SESSION HANDLER -----------------------------


class SessionHandler(threading.Thread):  # Distributor
    def __init__(self, address):
        threading.Thread.__init__(self)
        self.address = address


    def run(self):
        check_address_list(self.address)


def check_address_list(this_address):
    just_joined = True
    for address in addresses:
        if this_address == address:
            just_joined = False
    if just_joined is True:
        addresses.append(this_address)
        print("appended new address")


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
    print("sent package")


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
        packet_queue_non_ack.put([address, data_arr])


class RequestHandlerConnected(threading.Thread):  # Request Handler
    def __init__(self, this_addr):
        threading.Thread.__init__(self)
        self.this_addr = this_addr

    def run(self):
        handle_requests_connected(self.this_addr)


def handle_requests_connected(this_addr):
    sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock2.bind(this_addr)
    while True:
        data, address = sock2.recvfrom(4096)
        data_arr = pickle.loads(data)
        print('received"%s"' % repr(data_arr))
        # Put in queue
        packet_queue_ack.put([address, data_arr])


# --------- DISTRIBUTOR FOR NON ACK CLIENTS-----------------------------

class Distributor(threading.Thread):  # Distributor
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        distribute()


def distribute():
    process_list = [] # address, process_code
    watch_list = []
    init_time_var = True
    start = 0

    while True:
        # remove based on time thing

        if init_time_var == True:
            start = time.perf_counter()
            init_time_var = False
            print("init time")


        if (time.perf_counter() - start) >= 3 and watch_list.__len__() != 0:
            for i in watch_list:

                time_now = (time.perf_counter() - start)
                x = time_now - i[2]
                i[1] -= x
                i[2] = 0

            if i[1] <= 0:
                for q in process_list:
                    if q[0] == i[0]:
                        process_list.remove(q)
                        watch_list.remove(i)
                        print("removed idle address")

            start = time.perf_counter()


        new = True
        if packet_queue_non_ack.empty() is False:
            packet = packet_queue_non_ack.get()  # pop packet from que
            this_address = packet[0]  # address

            for i in process_list:
                    new = False
                    process_code = three_way_handshake(i[1], packet)

                    if process_code[0] == "kill":
                        process_list.remove(i)
                        print(process_list.__len__())
                        response_handler_thread = ResponseHandler(this_address, process_code[1])
                        response_handler_thread.start()
                        print("alocated and sent new port and threads for client")

                    elif process_code[0] == "bad":
                        print("removed process")
                        process_list.remove(i)
                        # should respond with generic code saying that process has been dropped

                    else:  # this is if it is an ongoing process succes.
                        process_list.remove(i)
                        response_handler_thread = ResponseHandler(this_address, process_code[1])
                        response_handler_thread.start()


            if new:
                process_code = three_way_handshake("hand-0", packet)
                if process_code[0] != "bad":
                    watch_list.append([this_address, 3, (time.perf_counter() - start)])
                    process_list.append([this_address, process_code[0]])
                    response_handler_thread = ResponseHandler(this_address, process_code[1])
                    response_handler_thread.start()
                else:
                    print("wrong init request")

# --------- DISTRIBUTOR FOR ACKNOWLEDGED CLIENTS-----------------------------

class DistributorAck(threading.Thread):  # Distributor
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        distribute_ack()


def distribute_ack():
    process_list = [] # address, process_code
    while True:
        new = True
        if packet_queue_ack.empty() is False:
            packet = packet_queue_ack.get()  # pop packet from que
            this_address = packet[0]  # address
            for i in process_list:

                if i[0] == this_address:
                    new = False
                    process_code = protocols_ack(i[1], packet)
                    print("it goes here")

                    if process_code[0] == "kill":
                        process_list.remove(i)
                        response_handler_thread = ResponseHandler(this_address, process_code[1])
                        response_handler_thread.start()


                    if process_code[0] == "bad":
                        print("removed process")
                        process_list.remove(i)
                        # should respond with generic code saying that process has been dropped


                    else:  # this is if it is an ongoing process succes.(chat true 06-05-2020)
                        i[1] = process_code[0] # assign this process the new process code
                        response_handler_thread = ResponseHandler(this_address, process_code[1])
                        response_handler_thread.start()

            if new:
                process_code = protocols_ack("chat-true", packet) # for now chat-true, but should be if-statements
                print(process_code[0])
                if process_code[0] != "bad":
                    process_list.append([this_address, process_code[0]])
                    response_handler_thread = ResponseHandler(this_address, process_code[1])
                    response_handler_thread.start()



# ------------------- PROTOCOLS --------------------------

def three_way_handshake(process_info, packet):

    head = extract_header(packet[1])
    payload = extract_payload(packet[1])

    if process_info == "hand-0":
        if head[2] == 1:
            if payload == "com-0":
                print("syn received ")
                our_head = set_flags(random.randint(1, 1001), head[0] + 1, 1, 0)
                load = "com-0 accept"
                cucumber = ["!", our_head, "?", load]
                data_string = pickle.dumps(cucumber)
                print("sending syn-ack to client")
                return ["hand-1", data_string]
            else:
                return ["bad", "none"]
        else:
            return ["bad", "none"]

    elif process_info == "hand-1":
        if head[2] == 0:
            if payload == "com-0 accept":
                our_head = set_flags(head[1], head[0] + 1, 0, 0)

                server_address_new = ('localhost', random.randint(49152, 65535))
                handle_requests_connected_thread = RequestHandlerConnected(server_address_new)
                handle_requests_connected_thread.start()

                load = server_address_new
                cucumber = ["!", our_head, "?", load]
                data_string = pickle.dumps(cucumber)
                print("three way handshake complete")
                return ["kill", data_string]
            else:
                return ["bad", "none"]
        else:
            return ["bad", "none"]

    else:
        return ["bad", "none"]

# ---------------------- PROTOCOL FOR ACKNOWLEDGED CLIENTS -------------------


def protocols_ack(process_info, packet):
    head = extract_header(packet[1])
    payload = extract_payload(packet[1])

    if process_info == "chat-true":
        our_head = set_flags(head[1], head[0] + 1, 0, 0)
        load = payload
        cucumber = ["!", our_head, "?", load]
        data_string = pickle.dumps(cucumber)
        print("responding to client msg")
        return ["chat-true", data_string]


    else:
        return ["bad", "none"]


# --------------- MAIN --------------------


request_handler_thread = RequestHandler()
distributor_thread = Distributor()
distribute_ack_thread = DistributorAck()

request_handler_thread.start()
distributor_thread.start()
distribute_ack_thread.start()







