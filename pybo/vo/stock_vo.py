
class StockVO:
    def __init__(self, code, name, time, cprice, diff, _open, high, low, offer, bid, vol, vol_value):
        self._code = code
        self._name = name
        self._time = time
        self._cprice = cprice
        self._diff = diff
        self._open = _open
        self._high = high
        self._low = low
        self._offer = offer
        self._bid = bid
        self._vol = vol
        self._vol_value = vol_value

    # Getters
    @property
    def code(self):
        return self._code

    @property
    def name(self):
        return self._name

    @property
    def time(self):
        return self._time

    @property
    def cprice(self):
        return self._cprice

    @property
    def diff(self):
        return self._diff

    @property
    def open(self):
        return self._open

    @property
    def high(self):
        return self._high

    @property
    def low(self):
        return self._low

    @property
    def offer(self):
        return self._offer

    @property
    def bid(self):
        return self._bid

    @property
    def vol(self):
        return self._vol

    @property
    def vol_value(self):
        return self._vol_value

    # Setters
    @code.setter
    def code(self, value):
        self._code = value

    @name.setter
    def name(self, value):
        self._name = value

    @time.setter
    def time(self, value):
        self._time = value

    @cprice.setter
    def cprice(self, value):
        self._cprice = value

    @diff.setter
    def diff(self, value):
        self._diff = value

    @open.setter
    def open(self, value):
        self._open = value

    @high.setter
    def high(self, value):
        self._high = value

    @low.setter
    def low(self, value):
        self._low = value

    @offer.setter
    def offer(self, value):
        self._offer = value

    @bid.setter
    def bid(self, value):
        self._bid = value

    @vol.setter
    def vol(self, value):
        self._vol = value

    @vol_value.setter
    def vol_value(self, value):
        self._vol_value = value

