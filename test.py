class player():

    def __init__(self, clientsocket, games, clients, counter):
        self.id = counter
        print("id: " + str(self.counter))
        self.socket = clientsocket
        self.pendingGames = games
        self.clients = clients
        self.state = 0

    def allOtherClients(self):
        clientlist = copy.copy(self.clients)
        clientlist.remove(self)
        return clientlist

    def send(self, message):
        self.socket.send(message)

    def decode_instruction(self, message):
        if message == "getPendingGames":
            if len(self.pendingGames) == 0:
                strmessage = "-"
            else:
                strmessage = ""
                for pendingGame in self.pendingGames:
                    strmessage = strmessage + str(pendingGame.id) + ";"
            self.send(strmessage)
            return
        if "createGame" in message:
            mapx = message[10:]
            createStruct = namedtuple("createStruct", "id ip0 ip1 ip2 ip3 map")
            iplist = self.socket.getpeername()[0].split(".")
            tuple_to_send = createStruct(id=self.id, ip0=int(iplist[0]), ip1=int(iplist[1]), ip2=int(iplist[2]), ip3=int(iplist[3]), map=mapx)
            str_to_send = struct.pack(create_format, *tuple_to_send._asdict().values())
            clients = self.allOtherClients()
            for client in clients:
                client.send("createGame" + str_to_send)
            return
        print(message)
        print("[INFO] Could not parse message")

player1 = player(None, [], [])
player2 = player(None, [], [])