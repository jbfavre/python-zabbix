class SenderException(Exception):

    def __init__(self, text):
        self.err_text = text
