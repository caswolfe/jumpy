import json
import logging
import uuid
from tkinter import *
from tkinter import filedialog, messagebox , simpledialog
import os
from threading import Thread
from time import sleep


from CodeFrame import CodeFrame
from DataPacket import DataPacket
from DataPacketDocumentEdit import DataPacketDocumentEdit, Action
from DataPacketRequestJoin import DataPacketRequestJoin
from DataPacketRequestResponse import DataPacketRequestResponse
from DataPacketSaveRequest import DataPacketSaveRequest
from NetworkHandler import NetworkHandler
from PySyntaxHandler import Syntax
from DataPacketCursorUpdate import DataPacketCursorUpdate
from DataPacketSaveDump import DataPacketSaveDump
from Workspace import Workspace


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
    current_directory = None
    current_terminal_buffer_column = 0
    current_terminal_buffer_line = 0
    current_file_name = StringVar()
    current_file = None
    old_text = ""

    # the workspace used by the program
    workspace: Workspace = None

    def __init__(self):

        self.net_hand = NetworkHandler(self.parse_message)
        self.cursor_thread_run = True
        self.cursor_thread = Thread(target=self.track_cursor)
        self.cursor_thread.setDaemon(True)
        self.u2_pos = None

        self.autosave_thread = Thread(target=self.autosave_thread)
        self.autosave_thread.setDaemon(True)


        self.log = logging.getLogger('jumpy')

        self.mac = hex(uuid.getnode())
        self.is_host = False
        self.have_perms = False

        self.workspace = Workspace()

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
        # self.menu_connections.add_command(label='Connect', command=self.net_hand.establish_connection)

        def create():
            if self.workspace.is_active:
                val = simpledialog.askstring("Lobby name", "Please name your lobby")
                self.net_hand.join_lobby(val)
                self.is_host = True
                self.have_perms = True
                self.net_hand.establish_connection()
            else:
                messagebox.showerror("jumpy", "no active workspace")

        def join():
            val = simpledialog.askstring("Lobby name", "Please input the lobby you want to join.")
            self.net_hand.join_lobby(val)
            self.net_hand.establish_connection()
            self.is_host = False
            self.have_perms = False
            dprj = DataPacketRequestJoin()
            self.net_hand.send_packet(dprj)

        self.menu_connections.add_command(label='Disconnect', command=self.net_hand.close_lobby)
        self.menu_connections.add_command(label='Create lobby', command=create)
        self.menu_connections.add_command(label='Join lobby', command=join)

        # add menubar to root
        self.root.config(menu=self.menu_bar)

        # terminal default
        self.terminal.insert("1.0","Console:\n>>>")
        self.current_terminal_buffer_column = 3
        self.current_terminal_buffer_line = 2

        #  text default
        self.old_text = self.code.text.get("1.0", END)

        # visual effects
        self.files.config(width=100, bg='light grey')
        self.terminal.config(height= 10, borderwidth=5)

        # visual packs
        self.root.geometry("900x600")
        self.top_frame.pack(side="top",fill='both', expand=True)
        self.bottom_frame.pack(side="bottom",fill='both', expand=True)        
        self.files.pack(side="left",fill='both')
        self.code.pack(side="right",fill='both', expand=True)
        self.terminal.pack(fill='both', expand=True)

    def show(self) -> None:
        """
        Shows the window.
        """
        # self.autosave_thread.start() # TODO: fix for better placing
        self.cursor_thread.start()
        self.root.mainloop()

    # TODO for folders with alot of files add a scrollbar
    def open_folder(self):
        location = filedialog.askdirectory()

        if location != "":
            self.current_directory = location
            #clear text and delete current radio buttons

            self.workspace.open_directory(location)

            # clear text and delete current radio buttons
            self.code.text.delete("1.0", END)
            self.update_workspace_radio_buttons()

            # folder = os.listdir(location)
            # for item in folder:
            #     item_path = location+ "/" + item
            #     # condition so that folders that start with "." are not displayed
            #     if os.path.isfile(item_path) or not item.startswith("."):
            #         Radiobutton(self.radio_frame, text = item, variable=self.current_file_name, command=self.open_item, value=item_path, indicator=0).pack(fill = 'x', ipady = 0)
            self.reset_terminal()

            # starts cursor tracking thread
            # TODO: uncomment

    def update_workspace_radio_buttons(self):
        self.radio_frame.destroy()
        self.radio_frame = Scrollbar(self.files, orient="vertical")
        self.radio_frame.pack()

        for item in self.workspace.files:
            item_path = self.workspace.directory + "/" + item
            self.log.debug('adding \'{}\' radio button...'.format(item_path))
            Radiobutton(self.radio_frame, text=item, variable=self.current_file_name, command=self.open_item, value=item_path, indicator=0).pack(fill='x', ipady=0)

    # TODO add functionality to clicking on folders (change current folder to that folder, have a back button to go to original folder) (chad doesn't think this is needed anymore)
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
            cursor_line, cursor_column = [int(x) for x in self.terminal.index(INSERT).split('.')]
            # handle terminal event
            #TODO pipe command to terminal, update buffer_column when pip output from terminal 
            if event.char == '\r':
                if self.current_directory:
                    self.terminal.insert(END,self.current_directory + ">")
                    self.current_terminal_buffer_column = len(self.current_directory) + 1
                else:
                    self.terminal.insert(END,">>>")
                self.current_terminal_buffer_line += 1
            if event.char == '\x03':
                self.reset_terminal()
            if cursor_column < self.current_terminal_buffer_column:
                if event.keycode == 37:
                    self.terminal.mark_set("insert", "%d.%d" % (self.current_terminal_buffer_line, cursor_column + 1))
                elif event.char == '\x08':
                    self.terminal.insert(END, ">")
            if cursor_line < self.current_terminal_buffer_line:
                    self.terminal.mark_set("insert", "%d.%d" % (cursor_line + 1, self.current_terminal_buffer_column))
        elif event.widget == self.code.text:
            # handle text event
            if self.net_hand.is_connected:
                # packet = DataPacketDocumentEdit(old_text=self.old_text, new_text=self.code.text.get("1.0", END))
                filename = "None"
                try:
                    filename = self.current_file_name.get().rsplit('/', 1)[1]
                except IndexError:
                    pass
                # packets: list[DataPacketDocumentEdit] = DataPacketDocumentEdit.generate_packets_from_changes(self.old_text, self.code.text.get("1.0", END), filename)
                packet = DataPacketDocumentEdit.generate_first_change_packet(self.old_text, self.code.text.get("1.0", END), filename)
                # for packet in packets:
                #     self.net_hand.send_packet(packet)
                self.net_hand.send_packet(packet)

            self.old_text = self.code.text.get("1.0", END)
            self.syntax_highlighting()

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
                    # self.log.debug(idx)
                    nums = idx.split('.')
                    nums = [int(x) for x in nums]
                    # self.log.debug(f"{left} { right}")
                    lastidx = '%s+%dc' % (idx, len(kw))
                    self.code.text.tag_add(color, idx, lastidx)
                    idx = lastidx

    def reset_terminal(self):
        self.terminal.delete("2.0",END)
        self.terminal.insert(END,"\n")
        if self.current_directory:
            self.terminal.insert(END,self.current_directory + ">")
            self.current_terminal_buffer_column = len(self.current_directory) + 1
        else:
            self.terminal.insert(END,">>>")
            self.current_terminal_buffer_column = 3
        self.current_terminal_buffer_line = 2

    def parse_message(self, packet_str: DataPacket):
        data_dict = json.loads(packet_str)
        packet_name = data_dict.get('packet-name')
        if data_dict.get('mac-addr') == self.mac:
            self.log.debug('received packet from self, ignoring...')
        else:
            self.log.debug('Received a \'{}\''.format(packet_name))
            print(data_dict)

            if packet_name == 'DataPacket':
                self.log.debug('Received a DataPacket')

            elif packet_name == 'DataPacketDocumentEdit':
                self.log.debug('Received a DataPacketDocumentEdit')
                self.log.debug(data_dict)
                result = self.workspace.apply_data_packet_document_edit(data_dict)
                if not result:
                    self.log.error('hash missmatch')
                    if self.is_host:
                        to_send = self.workspace.get_save_dump_from_document(data_dict.get('document'))
                        self.net_hand.send_packet(to_send)
                    else:
                        to_send = DataPacketSaveRequest()
                        to_send.define_manually(data_dict.get('document'))
                        self.net_hand.send_packet(to_send)
                self.log.debug('DataPacketDocumentEdit applied successful?')
                # text = self.code.text.get("1.0", END)
                # text_hash = DataPacketDocumentEdit.get_text_hash(text)
                # if text_hash == data_dict.get('old_text_hash'):
                #     self.log.debug("YEET")
                #     self.log.debug("Old Text: \'{}\"".format(text))
                #     self.code.text.delete("1.0", END)
                #     self.code.text.insert("1.0", DataPacketDocumentEdit.apply_packet_data_dict(data_dict.get('old_text_hash'), data_dict.get('action'), data_dict.get('position'), data_dict.get('character'), text_hash, text))
                #     self.code.text.delete('end-1c', 'end')
                #     self.log.debug("New Text: \'{}\"".format(self.code.text.get("1.0", END)))
                # else:
                #     self.log.error("FUCK")

            elif packet_name == 'DataPacketRequestJoin':
                if self.is_host:
                    result = messagebox.askyesno("jumpy request", "Allow \'{}\' to join the lobby?".format(data_dict.get('mac-addr')))
                    dprr = DataPacketRequestResponse()
                    dprr.define_manually(data_dict.get('mac_addr'), result)
                    self.net_hand.send_packet(dprr)
                    if result:
                        to_send = self.workspace.get_save_dump()
                        for packet in to_send:
                            self.net_hand.send_packet(packet)

            elif packet_name == 'DataPacketRequestResponse':
                self.log.debug('Received a DataPacketRequestResponse')
                can_join = data_dict.get('can_join')

                if can_join:
                    self.log.debug('allowed into the lobby')
                    self.workspace.use_temp_workspace()
                    self.have_perms = True
                    messagebox.showinfo("jumpy", "You have been accepted into the lobby!")
                else:
                    self.log.debug('rejected from the lobby')
                    self.have_perms = False
                    messagebox.showerror("jumpy", "You have NOT been accepted into the lobby...")
                    self.net_hand.close_connection()

            elif packet_name == 'DataPacketCursorUpdate':
                self.u2_pos = data_dict.get('position')

            elif packet_name == 'DataPacketSaveDump':
                packet = DataPacketSaveDump()
                packet.parse_json(packet_str)
                self.workspace.apply_data_packet_save_dump(packet)
                if self.workspace.new_file_added:
                    self.log.debug('new file added, updating radio buttons')
                    self.workspace.new_file_added = False
                    self.update_workspace_radio_buttons()
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
        cursor_1 = self.code.text.tag_config("c1", background='red')
        cursor_2 = self.code.text.tag_config("c2", background='blue')
        while self.cursor_thread_run:
            position = self.code.text.index(INSERT)
            pos_int = [int(x) for x in position.split(".")]
            end_pos = f'{pos_int[0]}.{pos_int[1]+1}'
            self.code.text.tag_add("c1", position, end_pos)
            # if self.u2_pos is not None:
            #     pos2 = self.u2_pos
            #     pos_int2 = [int(x) for x in pos2.split(".")]
            #     end_pos2 = f'{pos_int2[0]}.{pos_int2[1]+1}'
            #     self.code.text.tag_add("c2", pos2, end_pos2)
           # try:
              #  file = self.current_file_name.get().rsplit('/', 1)[1]
            dpcu = DataPacketCursorUpdate()
            dpcu.define_manually("None", position)
            #print(position, file)
            #self.log.debug(f"position {position} end pos {end_pos}")
            #sleep(1)
            #self.net_hand.send_packet(dpcu)
            #except Exception:
            #    print('No file open')
            # send position of cursor to others
            while not self.handle_event:
                sleep(1)
            self.code.text.tag_remove("c1",position, end_pos)
            #if self.u2_pos is not None:
            #    self.code.text.tag_remove("c1",pos2, end_pos2)

    def autosave_thread(self):
        while True:
            sleep(10)
            if self.is_host:
                self.log.debug("autosaving...")
                self.autosave()
                # p = DataPacketSaveDump()
                # file = None
                # try:
                #     file = self.current_file_name.get().rsplit('/', 1)[1]
                #
                # except Exception:
                #     print('No file open')
                # p.define_manually(file, self.code.text.get("1.0", END))
                # self.net_hand.send_packet(p)
                # # TODO: implement
                # # self.save_file()
            else:
                pass

    def autosave(self):
        if self.is_host:
            to_send = self.workspace.get_save_dump()
            for packet in to_send:
                self.net_hand.send_packet(packet)
