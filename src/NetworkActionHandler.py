import json
import logging
import uuid
from tkinter import END

from src.DataPacket import DataPacket
from src.DataPacketDocumentEdit import Action
from src import Window


class NetworkActionHandler:
    
    queue = None

    def __init__(self, window: Window):
        self.window = window
        self.log = logging.getLogger('jumpy')
        self.mac = hex(uuid.getnode())

    def parse_message(self, packet: DataPacket):
        data_dict = json.loads(packet)
        packet_name = data_dict.get('packet-name')
        if data_dict.get('mac-addr') == self.mac:
            self.log.debug('received packet from self, ignoring...')
        else:
            if packet_name == 'DataPacket':
                self.log.debug('Received a DataPacket')
            elif packet_name == 'DataPacketDocumentEdit':
                self.log.debug('Received a DataPacketDocumentEdit')
                self.log.debug(data_dict)
                action_str = data_dict.get('action')
                position_str = data_dict.get('position')
                character_str = data_dict.get('character')
                action = Action(int(action_str))
                position = int(position_str)
                self.window.update_text(action, position, character_str)
            else:
                self.log.warning('Unknown packet type: \'{}\''.format(packet_name))
