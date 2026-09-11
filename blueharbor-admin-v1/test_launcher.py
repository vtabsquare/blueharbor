import socket
import unittest
from contextlib import closing
from run_local import choose_ports


class PortTests(unittest.TestCase):
    def test_occupied_ports_get_distinct_alternatives(self):
        with closing(socket.socket()) as first, closing(socket.socket()) as second:
            first.bind(('127.0.0.1',0));first.listen()
            second.bind(('127.0.0.1',0));second.listen()
            occupied=(first.getsockname()[1],second.getsockname()[1])
            selected=choose_ports(*occupied)
            self.assertEqual(len(set(selected)),2)
            self.assertTrue(set(selected).isdisjoint(occupied))
            self.assertEqual(first.getsockname()[1],occupied[0])

    def test_free_ports_remain_preferred(self):
        ports=choose_ports(0,0)
        self.assertEqual(choose_ports(*ports),ports)

    def test_reservations_are_released(self):
        ports=choose_ports(0,0)
        with closing(socket.socket()) as first,closing(socket.socket()) as second:
            first.bind(('127.0.0.1',ports[0]))
            second.bind(('127.0.0.1',ports[1]))


if __name__=='__main__':unittest.main(verbosity=2)
