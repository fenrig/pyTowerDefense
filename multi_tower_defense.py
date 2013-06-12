#!/usr/bin/python
# -*- coding: latin-1 -*-
###################
# DOCS
# ----------------#
# http://inventwithpython.com/pygame/chapter2.html
# http://inventwithpython.com/pygame/chapter9.html
# http://www.pygame.org/docs/ref/event.html
# http://www.linuxformat.co.uk/wiki/index.php/Inkscape_-_master_gradients
# http://www.pygame.org/docs/ref/event.html
###################
# TODO:
#  * Extend routing:
#    - probably put in server thread
#  * Add enemy waves:
#    - http://www.pygame.org/docs/ref/time.html
#  * Create Destroy event
#    - http://www.pygame.org/docs/ref/event.html#pygame.event.Event
#    - http://stackoverflow.com/questions/2277925/custom-events-in-pygame
###################

import socket
import select
import pygame
import threading
import sys
from pygame.locals import *
import xml.etree.ElementTree as etree
import abc
import copy
from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4 import QtNetwork
import time
import struct
import copy
import random
from collections import namedtuple

UDP_DISCOVERY_PORT = 5005
LOBBY_PORT = 5006
GAME_PORT = 5007
CHAT_PORT = 5008

# Packet Stuff (only for packets with advanced information)
create_format = "IHHHH30s"

# lobbystuff
class player():

    def __init__(self, clientsocket, games, clients, counter):
        self.id = counter
        self.socket = clientsocket
        self.pendingGames = games
        self.clients = clients
        self.state = 0
        self.bln = True

    def allOtherClients(self):
        clientlist = copy.copy(self.clients)
        clientlist.remove(self)
        return clientlist

    def send(self, message):
        self.socket.send(message)

    def decode_instruction(self, message):
        print(message)
        if message == "getPendingGames":
            if len(self.pendingGames) > 0:
                for game in self.pendingGames:
                    strx = self.sendGame(game)
                    self.send(strx)
                    time.sleep(0.1)
            return
        if "createGame" in message:
            print("ok")
            mapx = message[10:]
            construction = {"id": int(self.id), "ip": self.socket.getpeername()[0], "map": mapx}
            self.pendingGames.append(construction)
            strx = self.sendGame(construction)
            clients = self.allOtherClients()
            for client in clients:
                print(client)
                client.send(strx)
            self.bln = False
            return
        if "deleteGame" in message:
            chosenid = int(message[10:])
            for game in self.pendingGames:
                if int(game["id"]) == chosenid:
                    clients = self.allOtherClients()
                    for client in clients:
                        client.send(message)
                    self.pendingGames.remove(game)
                    return
            return
        print(message)
        print("[INFO] Could not parse message")

    def sendGame(self, gamedict):
        createStruct = namedtuple("createStruct", "id ip0 ip1 ip2 ip3 map")
        iplist = gamedict["ip"].split(".")
        tuple_to_send = createStruct(id=gamedict["id"], ip0=int(iplist[0]), ip1=int(iplist[1]), ip2=int(iplist[2]), ip3=int(iplist[3]), map=gamedict["map"])
        str_to_send = "createGame" + struct.pack(create_format, *tuple_to_send._asdict().values())
        return str_to_send


def discoverLobby():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(0)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    timeoutcounter = 0
    while(True):
        sock.sendto("FIND-LOBBY", ("255.255.255.255", UDP_DISCOVERY_PORT))
        ready = select.select([sock], [], [], 1)
        if ready[0]:
            data, addr = sock.recvfrom(1024)
            if data == "PEDOT":
                return addr
        timeoutcounter = timeoutcounter + 1
        if timeoutcounter == 5:
            return False

def discoverUDPThread(udp_listen_socket):
    # UDP broadcast listener
    udp_listen_socket.bind(('<broadcast>', UDP_DISCOVERY_PORT))
    udp_listen_socket.setblocking(0)
    # UDP answer socket
    udp_send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # ----
    try:
        while True:
            result = select.select([udp_listen_socket], [], [], 1)
            if result[0]:
                msg, addr = result[0][0].recvfrom(56)
                msg = msg.decode("utf-8").strip()
                sys.stderr.write("[INFO] UDP Data: %s from %s:%s\n" % (msg, addr[0], addr[1]))
                if msg == "FIND-LOBBY":
                    udp_send_socket.sendto("PEDOT", (addr[0], addr[1]))
            if exitLock.acquire(False):
                exitLock.release()
                break
    finally:
        udp_send_socket.close()
        return

def lobbyClientThread(connection, client_address, clients, games, counter):
    # todo: complete this
    # todo: create player class
    # todo: create (pending) game class
    client = player(connection, games, clients, counter)
    clients.append(client)
    connection.setblocking(0)
    try:
        while True:
            ready = select.select([connection], [], [], 1)
            if ready[0]:
                data = connection.recv(4096)
                if data == '':
                    break
                client.decode_instruction(data)
            if exitLock.acquire(False):
                exitLock.release()
                break
    finally:
        clients.remove(client)
        if client.bln:
            for game in games:
                if game["id"] == client.id:
                    for client in clients:
                        client.send("deleteGame" + str(game["id"]))
                    games.remove(game)
                    break
        if connection:
            connection.close()
        return

def connectToLobby(ip_address):
    gamesinlobby = []
    while ip_address == False:
        ip_address = discoverLobby()
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect((ip_address[0], LOBBY_PORT))
    tcp_socket.setblocking(0)
    tcp_socket.send("getPendingGames")
    while True:
        ready = select.select([tcp_socket], [], [], 1)
        if ready[0]:
            data = tcp_socket.recv(4096)
            print(data)
            if data == '':
                connectToLobby(discoverLobby)
            elif "youNewServer" in data:
                counter = int(data[12:])
                time.sleep(2)
                hostLobby([], gamesinlobby, counter)
            elif "deleteGame" in data:
                number = int(data[10:])
                for element in gamesinlobby:
                    if element["id"] == number:
                        gamesinlobby.remove(element)
                        break
            elif "createGame" in data:
                createStruct = struct.unpack(create_format, data[10:])
                idx = createStruct[0]
                ipstr = str(createStruct[1]) + "." + str(createStruct[2]) + "." + str(createStruct[3]) + "." + str(createStruct[4])
                mapx = createStruct[5].strip()
                gamesinlobby.append({"id": int(idx),  "ip": ipstr, "map": mapx})
    tcp_socket.close()

def endThread(clients, games, tcpsock, udpsock, tcp_thread, udp_thread, counter):
    exitLock.acquire(True)
    print(len(clients))
    if len(clients) != 0:
        no = random.randint(0, (len(clients) - 1))
        client = clients[no]
        client.send("youNewServer" + str(counter))
    #newclients = client.allOtherClients()
    #ip = str(client.socket.getpeername()[0])
    #for c in newclients:
    #    c.send("newServer" + ip)
    exitLock.release()
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.connect(('localhost', LOBBY_PORT))
    tcp_socket.close()

def tcpLobbyThread(tcp_socket, clients, games, counter):
    tcp_socket.bind((('', LOBBY_PORT)))
    tcp_socket.listen(1)
    client_threads = []
    try:
        while(True):
            try:
                connection, client_address = tcp_socket.accept()
                client_threads.append(threading.Thread(target=lobbyClientThread, args=[connection, client_address, clients, games, counter]))
                client_threads[len(client_threads) - 1].start()
                counter = counter + 1
            finally:
                if exitLock.acquire(False):
                    exitLock.release()
                    break
    finally:
        tcp_socket.close()
        return


def hostLobby(clients, games, counter):
    # udp thread init
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # tcp thread init
    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # ------ threads
    udpthread = threading.Thread(target=discoverUDPThread, args=[udp_socket])
    udpthread.start()
    lobbythread = threading.Thread(target=tcpLobbyThread, args=[tcp_socket, clients, games, counter])
    lobbythread.start()
    endthread = threading.Thread(target=endThread, args=[clients, games, tcp_socket, udp_socket, lobbythread, udpthread, counter])
    endthread.start()


# -----------------
# QT STUFF
# http://doc.qt.digia.com/4.7/modelview.html
class game(object):
    def __init__(self, ide, ip, mapx):
        self.id = ide
        self.ip = ip
        self.map = mapx

    def __repr__(self):
        return "Game - %s %s %s" % (self.id, self.ip, self.map)


class lobbyItem(object):
    def __init__(self, item, header, parentItem):
        self.item = item
        self.parentItem = parentItem
        self.header = header
        self.childItems = []

    def appendChild(self, item):
        self.childItems.append(item)

    def child(self, row):
        return self.childItems[row]

    def childCount(self):
        return len(self.childItems)

    def columnCount(self):
        return 2

    def data(self, column):
        if self.item == None:
            if column == 0:
                return QtCore.QVariant(self.header)
            if column == 1:
                return QtCore.QVariant("")
        else:
            if column == 0:
                return QtCore.QVariant(self.item.id)
            if column == 1:
                return QtCore.QVariant(self.item.ip)
            if column == 2:
                return QtCore.QVariant(self.item.map)
        return QtCore.QVariant("")

    def parent(self):
        return self.parentItem

    def row(self):
        if self.parentItem:
            return self.parentItem.childItems.index(self)
        return 0


class lobbyModel(QtCore.QAbstractListModel):
    def __init__(self):
        super(lobbyModel, self).__init__()
        self.listdata = []
        self.horizontal_headers = ('ID', 'IP', 'MAP')
        self.rootItem = lobbyItem(None, "ALL", None)
        self.parents = {0: self.rootItem}

    def columnCount(self, parent=None):
        if parent and parent.isValid():
            return parent.internalPointer().columnCount()
        else:
            return len(self.horizontal_headers)

    def data(self, index, role):
        if not index.isValid():
            return QtCore.QVariant()

        item = index.internalPointer()
        if role == QtCore.Qt.DisplayRole:
            return item.data(index.column())
        if role == QtCore.Qt.UserRole:
            if item:
                return item.id

        return QtCore.QVariant()

    def headerData(self, column, orientation, role):
        if (orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole):
            try:
                return QtCore.QVariant(self.horizontal_headers[column])
            except IndexError:
                pass

        return QtCore.QVariant()

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parentItem = self.rootItem
        else:
            parentItem = parent.internalPointer()

        childItem = parentItem.child(row)
        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        childItem = index.internalPointer()
        if not childItem:
            return QtCore.QModelIndex()

        parentItem = childItem.parent()

        if parentItem == self.rootItem:
            return QtCore.QModelIndex()

        return self.createIndex(parentItem.row(), 0, parentItem)

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            p_Item = self.rootItem
        else:
            p_Item = parent.internalPointer()
        return p_Item.childCount()


class lobbyWindow(QtGui.QMainWindow):
    def __init__(self, ip_addr, glob):
        super(lobbyWindow, self).__init__()
        self.gamesinlobby = []
        self.initUI()
        self.initNetwork(ip_addr)
        self.state = 0
        self.glob = glob

    def __del__(self):
        self.socket.close()

    def initNetwork(self, ip_addr):
        # TODO: link signals
        # TODO: Add on disconnect net QTCPSocket
        # TODO: add to server a new lobby hoster
        self.socket = QtNetwork.QTcpSocket()
        self.socket.readyRead.connect(self.Read)
        self.socket.disconnected.connect(self.serverDisconnect)
        self.connectToServer(ip_addr)
        self.socket.waitForConnected()
        self.getpendinggames()

    def connectToServer(self, ip_addr):
        self.socket.connectToHost(ip_addr[0], LOBBY_PORT)

    def serverDisconnect(self):
        print("disconnect")
        ip = discoverLobby()
        if ip:
            self.connectToServer(ip)
        else:
            hostLobby([], [], 0)
            self.serverDisconnect()

    def Read(self):
        message = self.socket.readAll().data()
        print(message)
        if "deleteGame" in message:
            number = int(message[10:])
            for element in self.gamesinlobby:
                if element["id"] == number:
                    self.model.removeRows(element["num"], 1)
                    self.gamesinlobby.remove(element)
                    return
            return
        if "createGame" in message:
            createStruct = struct.unpack(create_format, message[10:])
            idx = createStruct[0]
            ipstr = str(createStruct[1]) + "." + str(createStruct[2]) + "." + str(createStruct[3]) + "." + str(createStruct[4])
            mapx = createStruct[5].strip()
            listx = [QtGui.QStandardItem(str(idx)), QtGui.QStandardItem(ipstr), QtGui.QStandardItem(mapx)]
            self.model.appendRow(listx)
            self.gamesinlobby.append({"id": int(idx),  "ip": ipstr, "map": mapx, "num": (self.model.rowCount() - 1)})
            return
        if "youNewServer" in message:
            counter = int(message[12:])
            time.sleep(2)
            hostLobby([], self.gamesinlobby, counter)
            return

    def initUI(self):
        q = QtGui.QWidget(self)
        self.setCentralWidget(q)
        # menubar actions
        self.joinAction = QtGui.QAction(QtGui.QIcon(), '&Join', self)
        self.joinAction.setShortcut('Ctrl+J')
        self.joinAction.setStatusTip('Join game')
        self.joinAction.triggered.connect(self.joinGame)
        self.createAction = QtGui.QAction(QtGui.QIcon(), '&Create', self)
        self.createAction.setShortcut('Ctrl+C')
        self.createAction.setStatusTip('Create Game')
        self.createAction.triggered.connect(self.createGame)
        self.singleAction = QtGui.QAction(QtGui.QIcon(), '&Single Player', self)
        self.singleAction.setShortcut('Ctrl+S')
        self.singleAction.setStatusTip('Play Single Player Game')
        self.singleAction.triggered.connect(self.singlePlayer)
        # menubar
        menubar = self.menuBar()
        actionMenu = menubar.addMenu('&Action')
        actionMenu.addAction(self.joinAction)
        actionMenu.addAction(self.createAction)
        actionMenu.addAction(self.singleAction)
        # toolbar
        self.toolbar = self.addToolBar('Actions')
        self.toolbar.addAction(self.joinAction)
        self.toolbar.addAction(self.createAction)
        self.toolbar.addAction(self.singleAction)
        # Statusbar
        self.statusBar().showMessage('Choose a game to join')
        # Listview
        self.lv = QtGui.QTreeView()
        self.lv.setMinimumSize(600, 400)
        self.model = QtGui.QStandardItemModel(0, 3)
        self.model.setHorizontalHeaderItem(0, QtGui.QStandardItem("ID"))
        self.model.setHorizontalHeaderItem(1, QtGui.QStandardItem("IP"))
        self.model.setHorizontalHeaderItem(2, QtGui.QStandardItem("MAP"))
        # item
        self.lv.setModel(self.model)
        # layout
        self.layout = QtGui.QVBoxLayout()
        self.layout.addWidget(self.lv)
        q.setLayout(self.layout)
        # ---------
        self.setWindowTitle('Lobby')
        self.show()

    def singlePlayer(self):
        items = []
        for key in maps.keys():
            items.append(str(key))
        item, ok = QtGui.QInputDialog.getItem(self, "Create Game", "Choose a map", items, 0, False)
        if ok:
            self.glob.chosenmap = str(item)
            QtCore.QCoreApplication.exit(3)
        return

    def joinGame(self):
        # TODO: complete joining a game
        # TODO: Delete game from lobby
        # TODO: Add changing lobby capability
        if len(self.lv.selectedIndexes()) > 0:
            index = self.lv.selectedIndexes()[0]
            chosenid = index.model().itemFromIndex(index).text()
            for game in self.gamesinlobby:
                if game["id"] == int(chosenid):
                    self.glob.connectip = game["ip"]
                    self.socket.write(str("deleteGame" + str(chosenid)))
                    self.socket.flush()
                    self.glob.chosenmap = game['map']
                    time.sleep(0.5)
                    QtCore.QCoreApplication.exit(2)
                    return

    def createGame(self):
        items = []
        for key in maps.keys():
            items.append(str(key))
        item, ok = QtGui.QInputDialog.getItem(self, "Create Game", "Choose a map", items, 0, False)
        if ok:
            self.socket.write("createGame" + str(item))
            self.socket.flush()
            self.joinAction.setEnabled(False)
            self.createAction.setEnabled(False)
            self.glob.chosenmap = str(item)
            QtCore.QCoreApplication.exit(1)

    def getpendinggames(self):
        self.socket.write("getPendingGames")
        self.socket.flush()


def gameFinder(ip_addr, glob):
    app = QtGui.QApplication(sys.argv)
    w = lobbyWindow(ip_addr, glob)
    return app.exec_()

# ----------------
# LOAD MAPS from XML
def parse_mapping_xml():
    tree = etree.parse('maps.xml')
    mapsroot = tree.getroot()

    maps = {}

    for maproot in mapsroot:
        obstacles = []
        for value in maproot:
            if value.tag == "obstacle":
                for loc in value:
                    if loc.tag == "x":
                        x = loc.text
                    elif loc.tag == "y":
                        y = loc.text
                obstacles.append((int(x), int(y)))
            elif value.tag == "destination":
                for loc in value:
                    if loc.tag == "x":
                        x = loc.text
                    elif loc.tag == "y":
                        y = loc.text
                destination = (int(x), int(y))
            elif value.tag == "origin":
                for loc in value:
                    if loc.tag == "x":
                        x = loc.text
                    elif loc.tag == "y":
                        y = loc.text
                origin = (int(x), int(y))
            elif value.tag == "title":
                title = value.text
        maps[title] = {"origin": origin, "destination": destination, "obstacles": obstacles}
    return maps


# ----------------
# Create route (dijkstra's algorithm)
def prepare_route():
    # extend
    # http://en.wikipedia.org/wiki/Dijkstra's_algorithm
    distance_dict = {}
    previous_dict = {}
    unvisited_list = []

    for x, v in enumerate(game_map):
        for y, z in enumerate(v):
            element = (x, y)
            distance_dict[element] = float('inf')
            previous_dict[element] = None
            unvisited_list.append(element)
    return distance_dict, previous_dict, unvisited_list


def neighbors(node):
    neighbor_list = []
    xoperation = [-1, 0, 1]
    yoperation = xoperation
    for xop in xoperation:
        if ((node[0] + xop) < 0) or ((node[0] + xop) > (len(game_map) - 1)):
                continue
        for yop in yoperation:
            if ((node[1] + yop) < 0) or ((node[1] + yop) > (len(game_map[0]) - 1)):
                continue
            x = (node[0] + xop)
            y = (node[1] + yop)
            if(game_map[x][y] == 0):
                neighbor_list.append((x, y))
    return neighbor_list


def create_route_map(startnode):
    '''
    Creates shortest route maps
    -----------------------------
    based on Dijkstra's Algorithm
    '''
    dist, prev, unvisited = prepare_route()

    dist[startnode] = 0

    while unvisited:
        shortest_node = unvisited[0]
        for node in unvisited:
            if dist[node] < dist[shortest_node]:
                shortest_node = node

        unvisited.remove(shortest_node)

        for neighbor in neighbors(shortest_node):
            new_distance = dist[shortest_node] + 1
            if new_distance < dist[neighbor]:
                dist[neighbor] = new_distance
                prev[neighbor] = shortest_node
    return prev


def create_route(startnode, endnode):
    prev = create_route_map(startnode)
    instruction_list = []
    instruction_list.append(endnode)
    for element in instruction_list:
        if (endnode[0] == element[0]) and (endnode[1] == element[1]):
            node = element
            break
    node = prev[endnode]
    while node is not None:
        instruction_list.append(node)
        node = prev[node]
    instruction_list.reverse()
    return instruction_list

# Extend when there is time :/ (for smoother animations)
'''
def extend_route(route):
    extended_route = []
    for index, node in enumerate(route):
        x = node[0] * 40
        y = node[1] * 40
        if index == 0:
            x = x + 20
            y = y + 20
            extended_route.append((x, y))
            if node[0] == route[index + 1][0]:
                if node[1] < route[index + 1][1]:
                    for i in range(1, 21):
                        # x = x + 1
                        y = y + 1
                        extended_route.append((x, y))
        # elif index == (len(route) - 1):
        else:
            if node[0] == route[index + 1][0]:

    return extended_route
'''


def extend_route(route):
    extended_route = []
    for node in route:
        x = (node[0] * 40) + 20
        y = (node[1] * 40) + 20
        extended_route.append((x, y))
    return extended_route


# ----------------
class enemy_base():
    __metaclass__ = abc.ABCMeta

    def __init__(self, pos, health):
        self.pos = pos
        self.health = health

    def move_on(self):
        self.pos = self.pos + 1

    def coordinaten(self, route):
        if self.pos < 0:
            return None
        if self.pos > (len(route) - 1):
            return float('inf')
        return route[self.pos]

    def destroy(self, destroyer, money_purse):
        if destroyer.owner:
            return (money_purse + self.worth)
        return money_purse

    def do_damage(self, damager, damage):
        self.health = self.health - damage
        if self.health < 1:
            pygame.event.post(pygame.event.Event(Die_Event, {'object': self, 'destroyer': damager}))


class basic_enemy(enemy_base):
    def __init__(self, pos, health):
        enemy_base.__init__(self, pos, health)
        self.worth = 20


class tower_base():
    __metaclass__ = abc.ABCMeta

    def __init__(self, x, y, owner):
        self.x = x
        self.y = y
        self.level = 0
        self.owner = owner

    def shoot(self, game_map):
        damage_power = self.damage[self.level][0]
        for enemy in self.enemies_to_shoot(game_map):
            enemy.do_damage(self, damage_power)

    # @abc.abstractmethod
    def upgradex(self, money_purse, self_activated):
        if (self.level + 1) < len(self.upgrade):
            if not self_activated:
                self.level = self.level + 1
            elif money_purse >= self.upgrade[self.level]:
                money_purse = money_purse - self.upgrade[self.level]
                self.level = self.level + 1
        return money_purse
        # pass

    @abc.abstractmethod
    def enemies_to_shoot(self, game_map):
        pass

    def buy(self, money_purse):
        return (money_purse - self.cost)

    def available_to_buy(self, money_purse):
        return (money_purse >= self.cost)


class shooter(tower_base):
    def __init__(self, x, y, owner):
        tower_base.__init__(self, x, y, owner)
        self.damage = [(2, 3), (3, 4), (3, 5), (4, 6)]
        self.cost = 30
        self.upgrade = [20, 40, 60]

    def enemies_to_shoot(self, game_map):
        damage_range = self.damage[self.level][0]
        enemies_in_range = []
        for x in range(0, (damage_range + 1)):
            for y in range(0, (damage_range + 1)):
                if x == 0 and y == 0:
                    continue
                xsom = self.x + x
                ysom = self.y + y
                if xsom >= 0 and xsom < len(game_map) and ysom >= 0 and ysom < len(game_map):
                    node = game_map[xsom][ysom]
                    if is_enemy(node):
                        enemies_in_range.append(node)
                xverschil = self.x - x
                yverschil = self.y - y
                if xverschil >= 0 and xverschil < len(game_map) and yverschil >= 0 and yverschil < len(game_map[0]):
                    node = game_map[xverschil][yverschil]
                    if is_enemy(node):
                        enemies_in_range.append(node)
        if enemies_in_range:
            target = enemies_in_range[0]
            for enemy in enemies_in_range:
                if target.pos < enemy.pos:
                    target = enemy
            return [target]
        return []

    def shoot_animation(self, game_map, surface, route):
        for enemy in self.enemies_to_shoot(game_map):
            pygame.draw.line(surface, FULL_RED, (self.x * 40 + 20, self.y * 40 + 20), (route[enemy.pos][0] * 40 + 20, route[enemy.pos][1] * 40 + 20))
        return surface


class ranger(tower_base):
    def __init__(self, x, y, owner):
        tower_base.__init__(self, x, y, owner)
        self.damage = [(2, 5), (3, 5), (3, 7)]
        self.cost = 50
        self.upgrade = [20, 40, 60]

    def enemies_to_shoot(self, game_map):
        damage_range = self.damage[self.level][0]
        enemies_in_range = []
        for x in range(0, (damage_range + 1)):
            for y in range(0, (damage_range + 1)):
                if x == 0 and y == 0:
                    continue
                xsom = self.x + x
                ysom = self.y + y
                if xsom >= 0 and xsom < len(game_map) and ysom >= 0 and ysom < len(game_map):
                    node = game_map[xsom][ysom]
                    if is_enemy(node):
                        enemies_in_range.append(node)
                xverschil = self.x - x
                yverschil = self.y - y
                if xverschil >= 0 and xverschil < len(game_map) and yverschil >= 0 and yverschil < len(game_map[0]):
                    node = game_map[xverschil][yverschil]
                    if is_enemy(node):
                        enemies_in_range.append(node)
        return enemies_in_range

    def shoot_animation(self, game_map, surface, route):
        damage_range = self.damage[self.level][0]
        hulp_range = (damage_range + damage_range + 1) * 40
        if self.enemies_to_shoot(game_map):
            pygame.draw.rect(surface, RANGE_BLUE, ((self.x - damage_range) * 40, (self.y - damage_range) * 40, hulp_range, hulp_range))
        return surface

class liner(tower_base):
    def __init__(self, x, y, owner):
        tower_base.__init__(self, x, y, owner)
        self.damage = [(2, 2), (3, 3), (4, 4)]
        self.cost = 40
        self.upgrade = [20, 40, 60]

    def enemies_to_shoot(self, game_map):
        damage_range = self.damage[self.level][0]
        enemies_in_range = []
        for x in range(0, (damage_range)):
            for y in range(0, (damage_range)):
                if x == 0 and y == 0:
                    continue
                xsom = self.x + x
                ysom = self.y + y
                if xsom >= 0 and xsom < len(game_map) and ysom >= 0 and ysom < len(game_map):
                    node = game_map[xsom][ysom]
                    if is_enemy(node):
                        enemies_in_range.append(node)
                xverschil = self.x - x
                yverschil = self.y - y
                if xverschil >= 0 and xverschil < len(game_map) and yverschil >= 0 and yverschil < len(game_map[0]):
                    node = game_map[xverschil][yverschil]
                    if is_enemy(node):
                        enemies_in_range.append(node)
        if enemies_in_range:
            target = enemies_in_range[0]
            for enemy in enemies_in_range:
                if target.pos < enemy.pos:
                    target = enemy
            for x, row in enumerate(game_map):
                for y, node in enumerate(row):
                    if node == target:
                        targetlocation = (x, y)

            selflocation = (self.x, self.y)
            offset = [targetlocation[0] - selflocation[0], targetlocation[1] - selflocation[1]]

            if offset[1] > 1:
                offset[1] = 1
            elif offset[1] < -1:
                offset[1] = -1

            if offset[0] > 1:
                offset[0] = 1
            elif offset[0] < -1:
                offset[0] = -1

            enemies = []
            if offset[0] < 0:
                maxx = 0
            elif offset[0] > 0:
                maxx = 14
            elif offset[0] == 0:
                maxx = selflocation[0] + 1
                offset[0] = 1

            if offset[1] < 0:
                maxy = 0
            elif offset[1] > 0:
                maxy = 14
            elif offset[1] == 0:
                maxy = selflocation[1] + 1
                offset[1] = 1

            for x in range(selflocation[0], maxx, offset[0]):
                for y in range(selflocation[1], maxy, offset[1]):
                    if is_enemy(game_map[x][y]):
                        enemies.append(game_map[x][y])
            return enemies
        return []

    def shoot_animation(self, game_map, surface, route):
        listx = self.enemies_to_shoot(game_map)
        if listx == []:
            return surface
        enemy = listx[(len(listx) - 1)]
        pygame.draw.line(surface, PURPLE, (self.x * 40 + 20, self.y * 40 + 20), (route[enemy.pos][0] * 40 + 20, route[enemy.pos][1] * 40 + 20))
        return surface


def is_enemy(node):
    typeval = type(node)
    if typeval == basic_enemy:
        return True
    return False

class globx():
    def __init__(self):
        self.connectip = ""
        self.chosenmap = ""

# Read xml
glob = globx()
maps = parse_mapping_xml()
# ----------------
# Colors
WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
RED = (255, 0, 0, 25)
FULL_RED = (255, 0, 0, 255)
RANGE_BLUE = (255, 0, 0, 75)
BLUE = (0, 0, 255, 150)
TRANSPARANT = (0, 0, 0, 0)
TRANS_WHITE = (0, 100, 100, 150)
PURPLE = (0xa0, 0x20, 0xf0)

# ---------------
# Initialise
exitLock = threading.Lock()
exitLock.acquire(False)


answer = discoverLobby()
if not answer:
    hostLobby([], [], 0)
    answer = discoverLobby()

qtresult = gameFinder(answer, glob)
enable_com = True
if qtresult == 0:
    exitLock.release()
    sys.exit()
game_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
chat_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
if qtresult == 1:
    game_socket.bind((('', GAME_PORT)))
    game_socket.listen(1)
    serverthread = threading.Thread(target=connectToLobby, args=[answer])
    serverthread.start()
    # lalal connectToLobby(ip_address)
    chat_socket.bind(('', CHAT_PORT))
    connection, client_address = game_socket.accept()
    game_socket = connection
    chat_con = (client_address[0], CHAT_PORT + 1)
elif qtresult == 2:
    game_socket.connect((glob.connectip, GAME_PORT))
    chat_con = (glob.connectip, CHAT_PORT)
    chat_socket.bind(('', CHAT_PORT + 1))
elif qtresult == 3:
    enable_com = False


typecolors = ((255, 0, 0), (0, 255, 0))

game_socket.settimeout(0.001)
chat_socket.settimeout(0.001)

chat_message_out = ''
chat_history = ['', '', '', '', '']
chat_history_owner = [0, 0, 0, 0, 0]

width_height = (802, 802)
pygame.init()
DISPLAYSURF = pygame.display.set_mode(width_height)
pygame.display.set_caption("Matthias Van Gestel - Computernetwerken Game")

# Splash Screen
#-----------------
splash_surface = pygame.Surface(width_height, pygame.SRCALPHA)
myfont = pygame.font.SysFont("tahoma", 35)
myfont.set_bold(True)
myfont.set_underline(True)
label = myfont.render("Von Gestel Design", 1, PURPLE)  # a020f0
DISPLAYSURF.blit(label, (130, 300))
pygame.display.update()

# Main Game
# ----------------
# picture objects
imagesdict = {'shooter': pygame.image.load('wirelesstower.png'), 'ranger': pygame.image.load('wifi2.png'), 'liner': pygame.image.load('wifi3.png')}

# Create grid on surface
base_surface = pygame.Surface(width_height, pygame.SRCALPHA)
base_surface.fill(BLACK)
for i in range(0, 602, 40):
    pygame.draw.line(base_surface, WHITE, (i, 0), (i, 600), 2)
for i in range(0, 602, 40):
    pygame.draw.line(base_surface, WHITE, (0, i), (600, i), 2)

myfont = pygame.font.SysFont("monospace", 15)
label = myfont.render("Money Bag:", 1, (0, 255, 0))
base_surface.blit(label, (615, 10))
label = myfont.render("Lives:", 1, (0, 255, 0))
base_surface.blit(label, (615, 30))
label = myfont.render("Wave:", 1, (0, 255, 0))
base_surface.blit(label, (615, 50))
label = myfont.render("Till Wave:", 1, (0, 255, 0))
base_surface.blit(label, (615, 70))

label = myfont.render("Object:", 1, (0, 255, 0))
base_surface.blit(label, (615, 120))
label = myfont.render("Level:", 1, (0, 255, 0))
base_surface.blit(label, (615, 140))
label = myfont.render(">", 1, (255, 255, 255))
base_surface.blit(label, (10, 780))

numberoftowers = 3
xoffset = 550
yoffset = 620
for i in range(0, 41, 40):
    pygame.draw.line(base_surface, WHITE, (yoffset, i + xoffset), (yoffset + (40 * numberoftowers), i + xoffset), 2)
for i in range(0, (40 * numberoftowers) + 1, 40):
    pygame.draw.line(base_surface, WHITE, (yoffset + i, xoffset), (yoffset + i, xoffset + 40), 2)

# mouse & window related
mousepos = (0, 0)
mouse_enabled = False

# dynamic surface (for alpha channels)
dyna_surface = pygame.Surface(width_height, pygame.SRCALPHA)
object_surface = pygame.Surface(width_height, pygame.SRCALPHA)
animation_surface = pygame.Surface(width_height, pygame.SRCALPHA)
update_objects = True

# game map
game_map = [[0 for i in range(40, 602, 40)]
            for j in range(40, 602, 40)]

# select map
glob.chosenmap = glob.chosenmap.strip('\x00')
origin = maps[glob.chosenmap]['origin']
destination = maps[glob.chosenmap]['destination']
for obstacle in maps[glob.chosenmap]['obstacles']:
    game_map[obstacle[0]][obstacle[1]] = -1
    pygame.draw.rect(base_surface, WHITE, ((obstacle[0] * 40) + 2, (obstacle[1] * 40) + 2, 38, 38))


# create route
route = create_route(origin, destination)
extended_route = extend_route(route)

# delay
pygame.time.wait(2000)

# -------------- kunstvar
money_purse = 100
lives = 10
enemy = 0

enemy_waves = [[basic_enemy(0, 15), basic_enemy(-1, 15), basic_enemy(-2, 15), basic_enemy(-3, 15)]]
enemy_waves.append([basic_enemy(0, 25), basic_enemy(-1, 25), basic_enemy(-2, 25), basic_enemy(-3, 25), basic_enemy(-4, 25)])
enemy_waves.append([basic_enemy(0, 30), basic_enemy(-1, 30), basic_enemy(-2, 30), basic_enemy(-3, 30), basic_enemy(-5, 30)])

wave_no = 0

extended_game_map = game_map
towers = []

last_selected = None

types = {shooter: 'shooter', ranger: 'ranger', liner: 'liner'}
create_towers = [shooter, ranger, liner]
ownerlist = {True: "You ARE the owner", False: "You are NOT the owner"}
wavecounter = 5
selected_sidebar_tower = 0
# --------------

# Create (game) timers:
#  30 FPS = 30 / 1000ms = 33.333333...ms
Die_Event = pygame.USEREVENT + 1
Tower_Event = pygame.USEREVENT + 5
TimerEvents = {'macro_move_event': (pygame.USEREVENT + 2), 'communication': (pygame.USEREVENT + 3), 'wave': (pygame.USEREVENT + 4)}
pygame.time.set_timer(TimerEvents['macro_move_event'], 1000)
pygame.time.set_timer(TimerEvents['wave'], 0)
pygame.time.set_timer(TimerEvents['communication'], 200)
# pygame.time.set_timer(TimerEvents['micro_move_event'], (1000/40))


while True:  # main game loop
    # Draw grid
    dyna_surface.blit(base_surface, (0, 0))
    # Draw objects in grid
    if update_objects:
        object_surface.fill(TRANSPARANT)
        x = 0
        for x, row in enumerate(game_map):
            for y, value in enumerate(row):
                typeval = type(value)
                if typeval == shooter:
                    object_surface.blit(imagesdict['shooter'], ((x * 40), (y * 40)))
                if typeval == ranger:
                    object_surface.blit(imagesdict['ranger'], ((x * 40), (y * 40)))
                if typeval == liner:
                    object_surface.blit(imagesdict['liner'], ((x * 40), (y * 40)))
        for loc in route:
            pygame.draw.rect(object_surface, BLUE, ((loc[0] * 40) + 2, (loc[1] * 40) + 2, 38, 38))
        update_objects = False

    for x, row in enumerate(extended_game_map):
        for y, value in enumerate(row):
            typeval = type(value)
            if typeval == basic_enemy:
                pygame.draw.circle(dyna_surface, (PURPLE), ((x * 40) + 20, (y * 40) + 20), 5, 0)

    animation_surface.fill(TRANSPARANT)
    for tower in towers:
        tower.shoot_animation(extended_game_map, animation_surface, route)  # self, game_map, surface, route

    # Side Pane
    label = myfont.render(str(money_purse) + " C", 1, (255, 0, 0))
    dyna_surface.blit(label, (710, 10))
    label = myfont.render(str(lives) + " <3", 1, (255, 0, 0))
    dyna_surface.blit(label, (710, 30))
    label = myfont.render('#' + str(wave_no), 1, (255, 0, 0))
    dyna_surface.blit(label, (710, 50))
    label = myfont.render(str(wavecounter) + 's', 1, (255, 0, 0))
    dyna_surface.blit(label, (710, 70))

    pygame.draw.rect(dyna_surface, TRANS_WHITE, (yoffset + 2 + (40 * selected_sidebar_tower), xoffset + 2, 38, 38))
    dyna_surface.blit(imagesdict['shooter'], (yoffset, xoffset))
    dyna_surface.blit(imagesdict['ranger'], (yoffset + 40, xoffset))
    dyna_surface.blit(imagesdict['liner'], (yoffset + 80, xoffset))

    if mouse_enabled:
        if mousepos[0] < 600 and mousepos[1] < 600:
            vakje = ((int(mousepos[0] / 40) * 40) + 2,
                    (int(mousepos[1] / 40) * 40) + 2, 38, 38)
            pygame.draw.rect(dyna_surface, RED, vakje)

            selected = game_map[int(mousepos[0] / 40)][int(mousepos[1] / 40)]
            if selected in towers:
                last_selected = selected

    if last_selected is not None:
        vakje = ((last_selected.x * 40) + 2,
                (last_selected.y * 40) + 2, 38, 38)
        pygame.draw.rect(dyna_surface, TRANS_WHITE, vakje)
        label = myfont.render(types[type(last_selected)], 1, (255, 0, 0))
        dyna_surface.blit(label, (710, 120))
        label = myfont.render(str(last_selected.level), 1, (255, 0, 0))
        dyna_surface.blit(label, (710, 140))
        label = myfont.render(ownerlist[last_selected.owner], 1, (255, 0, 0))
        dyna_surface.blit(label, (610, 160))

        #(mousepos[0] - (mousepos[0]%40) )
        # pygame.draw.circle(DISPLAYSURF, WHITE, mousepos, 20, 0)
    #Prioritize timer events:
    if pygame.event.get(TimerEvents['communication']):
        # TCP
        if enable_com:
            try: # catch timeout
                game_message = game_socket.recv(4096)
                if game_message == '':
                    enable_com = False
                else:
                    if game_message[:10] == 'TowerEvent':
                        poslist = game_message[10:].split(':')
                        pygame.event.post(pygame.event.Event(Tower_Event, {'button': 1, 'pos': (int(poslist[0]), int(poslist[1])), 'tower': int(poslist[2])}))
            except socket.timeout:
                pass
            try:
                chat_message = chat_socket.recv(4096)
                if chat_message == '':
                    enable_com = False
                chat_history[0] = chat_history[1]
                chat_history[1] = chat_history[2]
                chat_history[2] = chat_history[3]
                chat_history[3] = chat_history[4]
                chat_history[4] = "Other: " + chat_message
                chat_history_owner[0] = chat_history_owner[1]
                chat_history_owner[1] = chat_history_owner[2]
                chat_history_owner[2] = chat_history_owner[3]
                chat_history_owner[3] = chat_history_owner[4]
                chat_history_owner[4] = 1
            except socket.timeout:
                pass
    if pygame.event.get(TimerEvents['macro_move_event']):
        # move stip
        enemy = enemy + 1
        if enemy >= len(extended_route):
            enemy = 0
        extended_game_map = copy.deepcopy(game_map)
        for node in enemy_waves[wave_no]:
            node.move_on()
            loc = node.coordinaten(route)
            if loc == float('inf'):
                lives = lives - 1
                if lives < 1:
                    pygame.event.post(pygame.event.Event(QUIT, {}))
                node.pos = -1
            elif loc is not None:
                extended_game_map[loc[0]][loc[1]] = node
        for tower in towers:
            tower.shoot(extended_game_map)
    if pygame.event.get(TimerEvents['wave']):
        # enemy_no = 0
        wavecounter = wavecounter - 1
        if wavecounter == 0:
            pygame.time.set_timer(TimerEvents['wave'], 0)
            wave_no = wave_no + 1
            enemy_waves.append([basic_enemy(0, 30 + (wave_no * (10 + wave_no + wave_no))), basic_enemy(-1, 30 + (wave_no * (10 + wave_no + wave_no))), basic_enemy(-2, 30 + (wave_no * (10 + wave_no + wave_no))), basic_enemy(-3, 30 + (wave_no * (10 + wave_no + wave_no))), basic_enemy(-5, 30 + (wave_no * (10 + wave_no + wave_no)))])
            if wave_no == len(enemy_waves):
                wave_no = 0
            pygame.time.set_timer(TimerEvents['macro_move_event'], 1000)
            # maybe empty previous timer things
            wavecounter = 5
    for event in pygame.event.get():
        # print event
        if event.type == Die_Event:
            if event.object in enemy_waves[wave_no]:
                money_purse = event.object.destroy(event.destroyer, money_purse)
                enemy_waves[wave_no].remove(event.object)
                if len(enemy_waves[wave_no]) == 0:
                    pygame.time.set_timer(TimerEvents['wave'], 1000)
        elif event.type == ACTIVEEVENT:  # Don't draw mouse if mouse not in window
            if event.gain == 0:
                mouse_enabled = False
        elif event.type == MOUSEMOTION:  # Get mouse pos (event based)
            mouse_enabled = True
            mousepos = event.pos
        elif event.type == MOUSEBUTTONUP or event.type == Tower_Event:
            if event.button == 1:  # LEFT
                x, y = event.pos
                if x < 600 and y < 600:
                    x = x / 40
                    y = y / 40
                    selected = game_map[x][y]
                    if selected is 0:
                        if event.type == Tower_Event:
                            game_map[x][y] = create_towers[event.tower](x, y, False)
                        else:
                            game_map[x][y] = create_towers[selected_sidebar_tower](x, y, True)
                        selected = game_map[x][y]
                        update_objects = True
                        prev_route = route
                        route = create_route(origin, destination)
                        if event.type == MOUSEBUTTONUP and (len(route) < 2 or not selected.available_to_buy(money_purse)):
                            game_map[x][y] = 0
                            route = prev_route
                        else:
                            towers.append(selected)
                            extended_route = extend_route(route)
                            if enable_com:
                                if event.type == MOUSEBUTTONUP:
                                    game_socket.send('TowerEvent' + str(x*40+5) + ':' + str(y*40+5) + ':' + str(selected_sidebar_tower))
                                    money_purse = selected.buy(money_purse)
                    elif selected in towers:
                        old_purse = money_purse
                        if event.type == MOUSEBUTTONUP:
                            money_purse = game_map[x][y].upgradex(money_purse, True)
                        else:
                            money_purse = game_map[x][y].upgradex(money_purse, False)
                        if enable_com:
                            if old_purse != money_purse:
                                if event.type == MOUSEBUTTONUP:
                                    game_socket.send('TowerEvent' + str(x*40+5) + ':' + str(y*40+5) + ':-1')
                elif (y > xoffset) and (y < (xoffset + 40)) and (x > yoffset) and (x < (yoffset + (40 * numberoftowers))):
                    # print((y - xoffset) / 40)
                    selected_sidebar_tower = ((x - yoffset) / 40)
        elif event.type == QUIT:  # Quit application
            pygame.quit()
            exitLock.release()
            sys.exit()
        elif event.type == KEYDOWN:
            scancode = event.dict['scancode']
            if event.key == K_RETURN:
                chat_socket.sendto(chat_message_out, chat_con)
                chat_history[0] = chat_history[1]
                chat_history[1] = chat_history[2]
                chat_history[2] = chat_history[3]
                chat_history[3] = chat_history[4]
                chat_history[4] = "Me: " + chat_message_out
                chat_message_out = ''
                chat_history_owner[0] = chat_history_owner[1]
                chat_history_owner[1] = chat_history_owner[2]
                chat_history_owner[2] = chat_history_owner[3]
                chat_history_owner[3] = chat_history_owner[4]
                chat_history_owner[4] = 0
            elif event.key == K_SPACE:
                chat_message_out = chat_message_out + ' '
            elif event.key == K_BACKSPACE:
                chat_message_out = chat_message_out[: (len(chat_message_out) - 2)]
            elif scancode >= 24 and scancode <= 61 or scancode >= 10 and scancode <= 19 or scancode >= 79 and scancode <= 90:
                if len(chat_message_out) < 65:
                    chat_message_out = chat_message_out + event.unicode

            '''
            def upgrade(self, money_purse):
            if (self.level + 1) < len(self.upgrade):
                if money_purse >= self.upgrade[self.level]:
                    money_purse = money_purse - self.upgrade[self.level]
                    self.level = self.level + 1
            return money_purse
            # pass
            '''

    # Draw enemy
    # y = (route[enemy][1] * 40)  # + 20
    # y = (route[enemy][1] * 40)  # + 20
    # game_map[route]
    # pygame.draw.circle(dyna_surface, (PURPLE), (extended_route[enemy][0], extended_route[enemy][1]), 5, 0)
    # Combine surfaces
    label = myfont.render(chat_history[0], 1, typecolors[chat_history_owner[0]])
    animation_surface.blit(label, (15, 650))
    label = myfont.render(chat_history[1], 1, typecolors[chat_history_owner[1]])
    animation_surface.blit(label, (15, 675))
    label = myfont.render(chat_history[2], 1, typecolors[chat_history_owner[2]])
    animation_surface.blit(label, (15, 700))
    label = myfont.render(chat_history[3], 1, typecolors[chat_history_owner[3]])
    animation_surface.blit(label, (15, 725))
    label = myfont.render(chat_history[4], 1, typecolors[chat_history_owner[4]])
    animation_surface.blit(label, (15, 755))
    label = myfont.render(chat_message_out, 1, (255, 255, 255))
    animation_surface.blit(label, (20, 780))

    DISPLAYSURF.blit(dyna_surface, (0, 0))
    DISPLAYSURF.blit(object_surface, (0, 0))
    DISPLAYSURF.blit(animation_surface, (0, 0))
    # draw frame
    pygame.display.update()
