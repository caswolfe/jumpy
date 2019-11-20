import json
import logging
import uuid
from tkinter import *
from tkinter import filedialog, messagebox
import os
from threading import Thread
from time import sleep


from CodeFrame import CodeFrame
from DataPacket import DataPacket
from DataPacketDocumentEdit import DataPacketDocumentEdit, Action
from NetworkHandler import NetworkHandler
from PySyntaxHandler import Syntax
from DataPacketCursorUpdate import DataPacketCursorUpdate

class Window:
    """
    This class handles all display aspects of Jum.py.
    """

    # tk root
    root = Tk()

    # menu bar
    menu_bar = Menu()

    # file sub-menu in the menu bar
    menu_file = Menu(tearoff=False)

    # connections sub-menu in the menu bar
    menu_connections = Menu(tearoff=False)

    # frames for UX
    top_frame = Frame(root)
    bottom_frame = Frame(root)
    files = Frame(top_frame)

    # functional frames
    code = CodeFrame(top_frame)
    terminal = Text(bottom_frame)
    radio_frame = Scrollbar(files, orient="vertical")

    # other variables
    current_file_name = StringVar()
    current_file = None
    old_text = ""

    def __init__(self):

        self.net_hand = NetworkHandler(self.parse_message)
        self.cursor_thread_run = True
        self.cursor_thread = Thread(target=self.track_cursor)

        self.log = logging.getLogger('jumpy')

        self.mac = hex(uuid.getnode())

        self.create()

    def create(self) -> None:
        """
        Creates the window.
        """

        self.root.title("jum.py")
        self.root.bind('<Key>',self.handle_event)

        # menu bar
        self.menu_bar.add_cascade(label='File', menu=self.menu_file)
        self.menu_bar.add_cascade(label='Connections', menu=self.menu_connections)

        # file sub-menu
        self.menu_file.add_command(label="Open", command=self.open_folder)
        self.menu_file.add_command(label="Save", command=self.save_file)

        # connections sub-menu
        self.menu_connections.add_command(label='Connect', command=self.net_hand.establish_connection)
        self.menu_connections.add_command(label='Disconnect', command=self.net_hand.close_connection)

        # add menubar to root
        self.root.config(menu=self.menu_bar)

        # terminal default
        self.terminal.insert(1.0,"Console:\n>>> ")

        #  text default
        self.old_text = self.code.text.get("1.0", END)

        # visual effects
        self.files.config(width=100, bg='light grey')
        self.terminal.config(height= 10, borderwidth=5)

        # visual packs
        self.top_frame.pack(side="top",fill='both', expand=True)
        self.bottom_frame.pack(side="bottom",fill='both', expand=True)        
        self.files.pack(side="left",fill='both', expand=True)
        self.code.pack(side="right",fill='both', expand=True)
        self.terminal.pack(fill='both', expand=True)

    def show(self) -> None:
        """
        Shows the window.
        """
        self.root.mainloop()

    # TODO for folders with alot of files add a scrollbar, when file is changed clear terminal and change terminal directory (change ">>>" to "[directory path]>")
    def open_folder(self):
        location = filedialog.askdirectory()

        if location != "":

            # clear text and delete current radio buttons
            self.code.text.delete("1.0", END)
            self.radio_frame.destroy()
            self.radio_frame = Scrollbar(self.files, orient="vertical")
            self.radio_frame.pack()

            folder = os.listdir(location)
            for item in folder:
                item_path = location+ "/" + item 
                # condition so that folders that start with "." are not displayed
                if os.path.isfile(item_path) or not item.startswith("."):
                    Radiobutton(self.radio_frame, text = item, variable=self.current_file_name, command=self.open_item, value=item_path, indicator=0).pack(fill = 'x', ipady = 0)

            # starts cursor tracking thread
            # TODO: uncomment
            # self.cursor_thread.start()

    # TODO add functionality to clicking on folders (change current folder to that folder, have a back button to go to original folder)
    def open_item(self):
        if os.path.isfile(self.current_file_name.get()):
            self.code.text.delete("1.0", END)
            file = open(self.current_file_name.get(), "r")
            self.current_file = file
            try:
                self.code.text.insert(1.0, file.read())
                self.syntax_highlighting()
                self.old_text = self.code.text.get("1.0", END)
            except:
                self.code.text.insert(1.0,"Can not interperate this file")
            file.close()
        else:
            pass

    def save_file(self) -> None:
        f = filedialog.asksaveasfilename(defaultextension=".py")
        to_save_file = open(f, 'w')
        to_save_file.write(self.code.text.get("1.0", END))
        to_save_file.close()

    def update_text(self, action: Action, position: int, character: str):
        self.log.debug('updating text with action: \'{}\', position: \'{}\', character: \'{}\''.format(action, position, repr(character)))
        text_current = self.code.text.get("1.0", END)
        text_new = text_current[1:position+1] + character + text_current[position+1:]
        self.log.debug(f"current text:{repr(text_current)} \n updated text {repr(text_new)}")
        self.code.text.delete("1.0", END)
        self.code.text.insert("1.0", text_new)
        # n = 1
        # if action == Action.ADD:
        #     # TODO: fix#
        #     #
        #     text_new = character
        #     if text_new == "\n":
        #         n+=1
        #     self.log.debug("%d.%d"%(n,position))
        #     #self.text.insert("%d.%d"%(n,position), text_new)
        # elif action == Action.REMOVE:
        #     # TODO: implement
        #     pass

    def set_text(self, new_text: str):
        """
        Sets the text on the Text object directly.
        Author: Chad
        Args: new_text: string
        Returns: 
        """
        self.code.text.delete("1.0", END)
        self.code.text.insert("1.0", new_text)

    def handle_event(self, event):
        """
        Interpret keypresses on the local machine and send them off to be processed as
        a data packet. Keeps track of one-edit lag.
        TODO: Don't interpret all keypress as somthing to be sent e.g. don't send _alt_
        Authors: Chad, Ben
        Args: event: str unused?
        Returns:
        Interactions: sends DataPacketDocumentEdit
        """
        # if self.net_hand.is_connected:
        #     new_text = self.code.text.get("1.0", END)
        #     packet = DataPacketDocumentEdit(old_text=self.old_text, new_text=new_text)
        #     if packet.character == '' or new_text == self.old_text:
        #         return
        #     else:
        #         self.net_hand.send_packet(packet)
        # self.syntax_highlighting()
        # self.old_text = self.code.text.get("1.0", END)
        if event.widget == self.terminal:
            # handle terminal event
            #TODO pipe command to terminal, prevent editing previous lines
            if event.char == '\r':
                self.terminal.insert(END,">>> ")
            if event.char == '\x03':
                self.terminal.delete("2.4",END)
        elif event.widget == self.code.text:
            # handle text event
            if self.net_hand.is_connected:
                # packet = DataPacketDocumentEdit(old_text=self.old_text, new_text=self.code.text.get("1.0", END))
                filename = "None"
                try:
                    filename = self.current_file_name.get().rsplit('/', 1)[1]
                except IndexError:
                    pass
                packets: list[DataPacketDocumentEdit] = DataPacketDocumentEdit.generate_packets_from_changes(self.old_text, self.code.text.get("1.0", END), filename)
                for packet in packets:
                    self.net_hand.send_packet(packet)

            self.old_text = self.code.text.get("1.0", END)

    def syntax_highlighting(self, lang = 'python'):
        """
        Highlights key elements of syntax with a color as defined in the 
        language's SyntaxHandler. Only 'python' is currently implemented,   
        but more can easily be added in the future.
        Author: Ben
        Args: lang: string, which language to use
        Returns: 

        TODO: fix so keywords inside another keyword aren't highlighted
        TODO: make so that it doesn't trigger after every character
        TODO: run on seperate thread at interval or trigger (perhaps at spacebar? would reduce work)
        """
        for tag in self.code.text.tag_names():
            self.code.text.tag_delete(tag)
        if lang == 'python':
            SyntaxHandler = Syntax()

        syntax_dict = SyntaxHandler.get_color_dict()
        for kw in SyntaxHandler.get_keywords():
            idx = '1.0'
            color = syntax_dict[kw]
            self.code.text.tag_config(color, foreground=color)
           # search_term =#rf'\\y{kw}\\y'   # ' '+ kw + ' '
            while idx:
                idx = self.code.text.search('\\y' + kw +'\\y', idx, nocase=1, stopindex=END, regexp=True)
                if idx:
                    #self.log.debug(idx)    
                    nums = idx.split('.')
                    nums = [int(x) for x in nums]
                    #self.log.debug(f"{left} { right}")
                    lastidx = '%s+%dc' % (idx, len(kw))
                    self.code.text.tag_add(color, idx, lastidx)
                    idx = lastidx

    def parse_message(self, packet_str: DataPacket):
        data_dict = json.loads(packet_str)
        packet_name = data_dict.get('packet-name')
        print(packet_name)
        print(data_dict)
        if data_dict.get('mac-addr') == self.mac:
            self.log.debug('received packet from self, ignoring...')
        else:
            if packet_name == 'DataPacket':
                self.log.debug('Received a DataPacket')
            elif packet_name == 'DataPacketDocumentEdit':
                self.log.debug('Received a DataPacketDocumentEdit')
                self.log.debug(data_dict)
                text = self.code.text.get("1.0", END)
                text_hash = DataPacketDocumentEdit.get_text_hash(text)
                if text_hash == data_dict.get('old_text_hash'):
                    self.log.debug("YEET")
                    packet = DataPacketDocumentEdit()
                    packet.parse_json(packet_str)
                    self.log.debug("Old Text: \'{}\"".format(text))
                    self.code.text.delete("1.0", END)
                    self.code.text.insert("1.0", DataPacketDocumentEdit.apply_packet(text, packet))
                    self.log.debug("New Text: \'{}\"".format(self.code.text.get("1.0", END)))
                else:
                    self.log.error("FUCK")
                # action = Action(int(data_dict.get('action')))
                # time = data_dict.get('time-of-send')
                # self.log.debug(time)
                # action_str = data_dict.get('action')
                # position_str = data_dict.get('position')
                # character_str = data_dict.get('character')
                # action = Action(int(action_str))
                # position = int(position_str)
                # self.window.update_text(action, position, character_str)
                # self.window.set_text(data_dict.get('new_text'))
            else:
                self.log.warning('Unknown packet type: \'{}\''.format(packet_name))
                return False

    def get_words(self):
        """
        Gets all words (definition: seperated by a space character) in the
        Text object.
        Author: Ben
        Args: 
        Returns: words: list a list a words in the Text object
        """
        words = self.code.text.get("1.0", END).split(" ")
        return words

    def track_cursor(self):
        while self.cursor_thread_run:
            position = self.code.text.index(INSERT)
            try:
                file = self.current_file_name.get().rsplit('/', 1)[1]
                dpcu = DataPacketCursorUpdate()
                dpcu.define_manually(file, position)
                print(position, file)
                self.net_hand.send_packet(dpcu)
            except Exception:
                print('No file open')
            # send position of cursor to others
            sleep(1)

