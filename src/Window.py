import json
import logging
import uuid
from tkinter import *
from tkinter import filedialog, messagebox , simpledialog
import os
from threading import Thread
from time import sleep
import subprocess

import webbrowser

from DataPacketNameBroadcast import DataPacketNameBroadcast
from FilesFrame import FilesFrame

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

import shlex

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

    location = Frame(files)
    radio_frame = Frame(files)
    directory = Label(location)
    back = Button(location)

    # functional frames
    code = CodeFrame(top_frame)
    terminal = Text(bottom_frame)

    # other variables
    current_file_name = StringVar()
    current_file = None
    old_text = ""

    # the workspace used by the program
    workspace: Workspace = None

    def __init__(self):
        self.net_hand = NetworkHandler(self.parse_message)
        #self.cursor_thread_run = True
        #self.cursor_thread = Thread(target=self.track_cursor)
        #self.cursor_thread.setDaemon(True)
        #self.u2_pos = None
        self.names = {}
        self.cursor_colors = ['red', 'green', 'blue', 'yellow', 'cyan']

        self.autosave_thread = Thread(target=self.autosave_thread)
        self.autosave_thread.setDaemon(True)

        current_terminal_buffer_column = 0
        current_terminal_buffer_line = 0
        self.log = logging.getLogger('jumpy')

        self.mac = hex(uuid.getnode())
        self.is_host = False
        self.have_perms = False

        self.mac_name = dict()

        self.workspace = Workspace()

        self.create()

    def create(self) -> None:
        """
        Creates the window.
        """

        self.root.title("jum.py")
        self.root.bind('<Key>',self.handle_event)
        self.root.bind('<Button-1>',self.handle_event)

        # menu bar
        self.menu_bar.add_cascade(label='File', menu=self.menu_file)
        self.menu_bar.add_cascade(label='Connections', menu=self.menu_connections)

        # file sub-menu
        self.menu_file.add_command(label="Open", command=self.open_folder)
        self.menu_file.add_command(label="Save", command=self.save_file)
        self.menu_file.add_command(label="Help", command=self.open_help)

        # connections sub-menu
        # self.menu_connections.add_command(label='Connect', command=self.net_hand.establish_connection)

        def create():
            if self.workspace.is_active:
                val = simpledialog.askstring("Lobby name", "Please name your lobby")
                username = simpledialog.askstring("Prompt", "Please input a username")
                self.mac_name.update({self.mac: username})
                self.net_hand.join_lobby(val)
                self.is_host = True
                self.have_perms = True
                self.net_hand.establish_connection()
                self.back.config(state='disabled')
            else:
                messagebox.showerror("jumpy", "no active workspace")

        def join():
            self.workspace.use_temp_workspace()
            self.open_folder(self.workspace.directory)
            self.code.text.config(state='disabled')
            val = simpledialog.askstring("Lobby name", "Please input the lobby you want to join.")
            username = simpledialog.askstring("Prompt", "Please input a username")
            self.mac_name.update({self.mac: username})
            self.net_hand.join_lobby(val)
            self.net_hand.establish_connection()
            self.is_host = False
            self.have_perms = False
            dprj = DataPacketRequestJoin()
            dprj.set_name(self.mac_name.get(self.mac))
            self.net_hand.send_packet(dprj)

        def disconnect():
            self.net_hand.close_lobby()
            self.back.config(state='normal')

        self.menu_connections.add_command(label='Disconnect', command=disconnect)
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

        self.directory.config(width=20,text="Current Folder:\nNone")
        self.back.config(text="cd ..\\",command=self.previous_dir)

        # visual effects
        self.files.config(width=200, bg='light grey')
        self.terminal.config(height= 10, borderwidth=5)

        # visual packs
        self.root.geometry("900x600")

        self.top_frame.pack(side="top",fill='both', expand=True)
        self.bottom_frame.pack(side="bottom",fill='both', expand=True) 

        self.files.pack(side="left",fill='both')
        self.location.pack(side="top",fill='x')
        self.directory.pack(side="left",fill='x', expand=True)
        self.back.pack(side="right",fill='x',expand=True)
       
        self.code.pack(side="right",fill='both', expand=True)
        self.terminal.pack(fill='both', expand=True)

    def show(self) -> None:
        """
        Shows the window.
        """
        # self.autosave_thread.start() # TODO: fix for better placing
        #self.cursor_thread.start()
        self.root.mainloop()
        
    def previous_dir(self):
        if self.workspace.directory != "C:/" and self.workspace.directory:
            split = self.workspace.directory.split("/")
            new_dir = "/".join(split[0:-1])
            if(new_dir == "C:"):
                new_dir += "/"
            self.open_folder(new_dir)

    def open_help(self):
        webbrowser.open_new("https://docs.google.com/document/d/13AHTV3BVfS3ELmaW2cqfzgJ9YmOeBkkkMqViyU-0WDM/edit?usp=sharing")

    # TODO for folders with alot of files add a scrollbar
    def open_folder(self, folder=None):
        if self.net_hand.is_connected:
            self.back.config(state='disabled')
        else:
            self.back.config(state='normal')
        location = ""
        if folder:
            location = folder
        else:
            location = filedialog.askdirectory()

        if location != "":
            #clear text and delete current radio buttons

            self.workspace.open_directory(location)

            # clear text and delete current radio buttons
            self.code.text.delete("1.0", END)

            # folder = os.listdir(location)
            # for item in folder:
            #     item_path = location+ "/" + item
            #     # condition so that folders that start with "." are not displayed
            #     if os.path.isfile(item_path) or not item.startswith("."):
            #         Radiobutton(self.radio_frame, text = item, variable=self.current_file_name, command=self.open_item, value=item_path, indicator=0).pack(fill = 'x', ipady = 0)
            split = str(location).split("/")
            index = -1
            folder_name = split[index]
            while folder_name == "":
                index -= 1
                folder_name = split[index]
            self.directory.config(text="Current Folder:\n" + folder_name)
            # clear text and delete current radio buttons
            self.code.text.delete("1.0", END)
            self.radio_frame.destroy()
            self.radio_frame = Frame(self.files,width=self.files.cget("width"))
            self.radio_frame.pack(fill="both",expand=True)
            self.options = FilesFrame(self.radio_frame,window = self)
            self.options.populate(self.workspace)
            self.reset_terminal()

            # starts cursor tracking thread
            # TODO: uncomment

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
            self.open_folder(self.current_file_name.get())
            name = self.current_file_name.get().split("/")[-1]
            self.directory.config(text="Current Folder:\n" + name)

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
            
            cursor_line, cursor_column = [int(x) for x in self.terminal.index(INSERT).split('.')]

            if event.char == '\r':
                command = self.terminal.get(str(self.current_terminal_buffer_line) + "." + str(self.current_terminal_buffer_column),END).strip("\n ").split(" ")
                print(command)
                if command[0] != "":
                    if self.workspace.directory:
                        os.chdir(self.workspace.directory)
                        if "cd" in command:
                            if not self.net_hand.is_connected:
                                if len(command) >= 2:
                                    try:
                                        os.chdir(self.workspace.directory + "/" + " ".join(command[1::]).strip('\'\"'))
                                        self.workspace.open_directory(os.getcwd().replace("\\","/"))
                                        self.open_folder(self.workspace.directory)
                                        return
                                    except:
                                        self.current_terminal_buffer_line += 1
                                        self.terminal.insert(END,"'" + " ".join(command[1::]).strip('\'\"') + "' does not exist as a subdirectory\n")
                                else:
                                    os.chdir("C:/")
                                    self.workspace.open_directory(os.getcwd())
                                    self.open_folder("C:/")
                                    return
                            else:
                                self.terminal.insert(END, "Can not change directories while in workspace.\n")
                                self.current_terminal_buffer_line += 1
                        else:
                            error = self.run_command(" ".join(command))
                            if error:
                                self.terminal.insert(END, error)
                                self.current_terminal_buffer_line += 1
                    else:
                        self.terminal.insert(END, "Open a directory before using the console.\n")
                        self.current_terminal_buffer_line += 1

                if self.workspace.directory:
                    self.terminal.insert(END,self.workspace.directory + ">")
                    self.current_terminal_buffer_column = len(self.workspace.directory) + 1
                else:
                    self.terminal.insert(END,">>>")
                self.terminal.see(END)
                self.current_terminal_buffer_line += 1
                return
            if event.char == '\x03':
                self.reset_terminal()
            if cursor_column < self.current_terminal_buffer_column or cursor_line < self.current_terminal_buffer_line:
                if event.char == '\x08':
                    self.terminal.insert(END,">")
                self.terminal.mark_set("insert", "%d.%d" % (self.current_terminal_buffer_line, self.current_terminal_buffer_column))
        elif event.widget == self.code.text:
            # handle text event

            if self.net_hand.is_connected and self.current_file_name.get() != "None":
                to_send = DataPacketDocumentEdit()
                to_send.set_document(self.current_file_name.get().split('/')[-1])
                to_send.set_text(self.code.text.get("1.0", END))
                self.net_hand.send_packet(to_send)

                # send a DataPacketCursorUpdate
                position = self.code.text.index(INSERT)
                dpcu = DataPacketCursorUpdate()
                dpcu.set_position(position)
                dpcu.set_document(self.current_file_name.get().split('/')[-1])
                self.net_hand.send_packet(dpcu)

            self.syntax_highlighting()

            # # TODO: chad thinks that this is the answere to hash mis-match
            sleep(0.1)

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
        self.code.text.tag_config("comments", foreground = "olive drab")
        idx = '1.0'
        while idx != '':
            idx = self.code.text.search('#', idx, nocase=1, stopindex=END)
            #self.log.debug(idx)
            if idx == '':
                #self.log.debug(idx)
                continue
            #self.log.debug(idx)
            endl = self.code.text.search('\n', idx, stopindex=END)
            if endl == "":
                endl = END
            self.code.text.tag_add("comments", idx, endl)
            idx = endl

    def reset_terminal(self):
        self.terminal.delete("1.0",END)
        self.terminal.insert(END,"Console:\n")
        if self.workspace.directory:
            self.terminal.insert(END,self.workspace.directory + ">")
            self.current_terminal_buffer_column = len(self.workspace.directory) + 1
        else:
            self.terminal.insert(END,">>>")
            self.current_terminal_buffer_column = 3
        self.current_terminal_buffer_line = 2

    def run_command(self, command):
        try:
            process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE)
            while True:
                output = process.stdout.readline()
                if output == bytes('',"utf-8") and process.poll() == 0:
                    break
                if output:
                    self.terminal.insert(END,output.strip() + bytes("\n","utf-8"))
                    self.current_terminal_buffer_line += 1
            self.terminal.insert(END,"\n")
            self.current_terminal_buffer_line += 1
        except:
            return "'" + command + "' is not a valid command\n"

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

                cursor_index = self.code.text.index(INSERT)

                packet: DataPacketDocumentEdit = DataPacketDocumentEdit()
                packet.parse_json(packet_str)
                self.workspace.apply_data_packet_document_edit(packet)
                current_doc = self.current_file_name.get().split('/')[-1]
                if packet.get_document() == current_doc:
                    self.code.text.delete("1.0", END)
                    self.code.text.insert(END, packet.get_text())
                    self.syntax_highlighting()

                self.code.text.mark_set(INSERT, cursor_index)

            elif packet_name == 'DataPacketCursorUpdate':
                u2_pos = data_dict.get('position')
                name = data_dict.get('mac-addr')
                self.cursor_update(u2_pos, str(name))


            elif packet_name == 'DataPacketRequestJoin':
                packet: DataPacketRequestJoin = DataPacketRequestJoin()
                packet.parse_json(packet_str)
                if self.is_host:
                    result = messagebox.askyesno("jumpy request", "Allow \'{}\' to join the lobby?".format(data_dict.get(DataPacketRequestJoin.KEY_NAME)))
                    dprr = DataPacketRequestResponse()
                    dprr.set_target_mac(packet.get_mac_addr())
                    dprr.set_can_join(result)
                    self.net_hand.send_packet(dprr)
                    if result:
                        sleep(3)
                        name_broadcast = DataPacketNameBroadcast()
                        name_broadcast.set_name(self.mac_name.get(self.mac))
                        self.net_hand.send_packet(name_broadcast)
                        to_send = self.workspace.get_save_dump()
                        for packet in to_send:
                            self.net_hand.send_packet(packet)

            elif packet_name == 'DataPacketRequestResponse':
                packet: DataPacketRequestResponse = DataPacketRequestResponse()
                packet.parse_json(packet_str)
                if packet.get_target_mac() == DataPacket.get_mac_addr_static():
                    self.log.debug('Received a DataPacketRequestResponse')
                    can_join = packet.get_can_join()

                    # todo: fix
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

                name_broadcast = DataPacketNameBroadcast()
                name_broadcast.set_name(self.mac_name.get(self.mac))
                self.net_hand.send_packet(name_broadcast)

            
            elif packet_name == 'DataPacketSaveDump':
                packet: DataPacketSaveDump = DataPacketSaveDump()
                packet.parse_json(packet_str)
                self.workspace.apply_data_packet_save_dump(packet)
                if self.workspace.new_file_added:
                    if len(self.workspace.files) == packet.get_workspace_size():
                        self.log.debug('received whole workspace, setting code.text state to normal')
                        self.code.text.config(state='normal')
                        self.open_folder(self.workspace.directory)

            elif packet_name == 'DataPacketSaveRequest':
                to_send = self.workspace.get_save_dump_from_document(data_dict.get('document'))
                self.net_hand.send_packet(to_send)

            elif packet_name == 'DataPacketNameBroadcast':
                packet = DataPacketNameBroadcast()
                packet.parse_json(packet_str)
                self.log.debug('mac_name updating {} to {}'.format(packet.get_mac_addr(), packet.get_name()))
                self.mac_name.update({packet.get_mac_addr(): packet.get_name()})

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
    def cursor_update(self, pos, name):
        if name not in self.names:
            self.names[name] = self.cursor_colors.pop()
        color = self.names[name]
        print(color)
        self.code.text.tag_remove(color,"1.0", END)
        curs = self.code.text.tag_config(color, background=color)
        pos_int = [int(x) for x in pos.split(".")]
        end_pos = f'{pos_int[0]}.{pos_int[1]+1}'
        self.code.text.tag_add(color, pos, end_pos)
        
    def autosave_thread(self):
        while True:
            sleep(10)
            if self.is_host:
                self.log.debug("autosaving...")
                self.autosave()
            else:
                pass

    def autosave(self):
        if self.is_host:
            to_send = self.workspace.get_save_dump()
            for packet in to_send:
                self.net_hand.send_packet(packet)
