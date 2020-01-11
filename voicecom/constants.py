#maximum amount of OPUS packets stored per voice socket
MAX_BUFFER_SIZE = 6

#amount of OPUS packets to keep if the buffer is cleared out due it reaching its maximum capacity
HIGH_BUFFER_SIZE = 3

#minimum amount of OPUS packets stored per voice socket.
#Used to make sure there is still enough space in the buffer to fix message order and properly time the frames.
MIN_BUFFER_SIZE = 1

#Threshold for jitter buffer, in samples. Depends on MIN_BUFFER_SIZE, lower is more responsive but less reliable
JITTER_THRESHOLD = 3000