import os, socket, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestNoNetwork(unittest.TestCase):
    def test_full_pipeline_runs_with_sockets_blocked(self):
        real = socket.socket
        def blocked(*a, **k): raise AssertionError("network access attempted")
        socket.socket = blocked
        try:
            from report import build_report
            self.assertEqual(build_report()["total_cases"], 5)
        finally:
            socket.socket = real

if __name__ == "__main__": unittest.main()
