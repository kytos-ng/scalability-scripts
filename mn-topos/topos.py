"""Mininet custom topos."""

from mininet.topo import Topo


class Ring3(Topo):
    "Simple topology example."

    def build(self):
        "Create custom topo."

        # Add hosts and switches
        h11 = self.addHost("h11")
        h12 = self.addHost("h12")
        h2 = self.addHost("h2")
        h3 = self.addHost("h3")

        s1 = self.addSwitch("s1")
        s2 = self.addSwitch("s2")
        s3 = self.addSwitch("s3")

        self.addLink(s1, h11)
        self.addLink(s1, h12)
        self.addLink(s2, h2)
        self.addLink(s3, h3)

        self.addLink(s1, s2)
        self.addLink(s2, s3)
        self.addLink(s1, s3)



topos = {"ring3": (lambda: Ring3())}
