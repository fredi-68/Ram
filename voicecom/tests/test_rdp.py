from unittest import TestCase

from ..rdp import VoicePacket

class TestRDP(TestCase):

    HEADER = bytes([0x80, 0x78, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    PAYLOAD = bytes([0x01, 0x02, 0x03, 0x04])

    TEST_DATA = HEADER + PAYLOAD

    def test_voice_packet_init(self):

        packet = VoicePacket(self.TEST_DATA)
        self.assertEqual(packet.data, self.PAYLOAD)
        self.assertEqual(packet.type, 0x80)
        self.assertEqual(packet.version, 0x78)
        self.assertEqual(packet.timestamp, 0x00)
        self.assertEqual(packet.ssrc, 0x00)

    def test_voice_packet_encoding(self):

        packet = VoicePacket(self.TEST_DATA)
        self.assertEqual(packet.to_bytes(), self.TEST_DATA)