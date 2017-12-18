

class Member:
    def __init__(self, dn, fn,  uid):
        self.floor = None
        self.display_name = dn
        self.first_name = fn
        self.user_id = uid
        self.channel_id = None
        self.token = None
        self.state = None