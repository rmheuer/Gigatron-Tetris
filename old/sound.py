from asm import *
import math

# VGA Timing:
#   Horizontal:    Cycles  Start time
#     Visible:     160     36
#     Front Porch: 4       196
#     Sync:        24      0
#     Back Porch:  12      24
#     Total:       200
#   Vertical:
#     Visible: 480
#     Front Porch: 10
#     Sync: 2
#     Back Porch: 33
#     Total: 525

hSync = 0x40
vSync = 0x80
syncBits = hSync | vSync

vFrontTime = 10
vSyncTime = 2
vBackTime = 33

xout = zpByte()

nextVideo = zpByte()
videoLine = zpByte()
videoScroll = zpByte()
videoSync_hSync = zpByte()
videoSync_idle = zpByte()

nextSound = zpByte()
soundOut = zpByte()
soundTimerLo = zpByte(4)
soundTimerHi = zpByte(4)
soundIntervalLo = zpByte(4)
soundIntervalHi = zpByte(4)
soundOsc = zpByte(4)
soundVolume = zpByte(4)

nextCodeLo = zpByte()
nextCodeHi = zpByte()

musicPointerHi = 251
musicPointerLo = 252
musicTimer = 253
musicInstruction = 254
musicDuration = 255
musicChannel = zpByte()

# Use for loops
index = zpByte()

SAMPLE_RATE = 525 * 60 / 4.0
def calcTickInterval(freq):
    return round(SAMPLE_RATE / (2 * freq) * 128) / 128.0

def calcTimerHi(freq):
    return math.floor(calcTickInterval(freq))

def calcTimerLo(freq):
    return int((calcTickInterval(freq) % 1) * 128)

# ROM page 0: Initialization
align(0x100, 0x100)

ld('visible1')
st([nextVideo])
ld(1)
st([videoLine])
ld(0)
st([videoScroll])
ld(syncBits ^ hSync)
st([videoSync_hSync])
ld(syncBits)
st([videoSync_idle])

ld('sound1')
st([nextSound])
for i in range(4):
    ld(255)
    st([soundTimerHi + i])
    ld(127)
    st([soundTimerLo + i])
    ld(0)
    st([soundOsc + i])
    st([soundVolume + i])

# Enable channels
ld(3 << 4)
st([soundVolume])
st([soundVolume + 1])
st([soundVolume + 2])
st([soundVolume + 3])

ld(120)
st([index])
ld(hi('clearScreen'))
st([nextCodeHi])
ld(lo('clearScreen'))
st([nextCodeLo])

ld(4)
st([musicChannel])
label('musicSetup.loop')
ld([musicChannel])
ld(AC, Y)
st([Y, musicPointerHi])
ld(0)
st([Y, musicPointerLo])
st([Y, musicTimer])
ld([musicChannel])
suba(1)
bne('musicSetup.loop')
st([musicChannel])

ld(hi('loadMusic'), Y)
jmp(Y, 'loadMusic')
nop()
label('loadMusic_return')

# Enter the video/audio loop
ld(hi('oscillators'), Y)
jmp(Y, [nextSound])
nop()

# ROM pages 1 & 2: Video and Sound
align(0x100, 0x200)

def oscillator(channel, nextChannel):
    timerLo = soundTimerLo + channel
    timerHi = soundTimerHi + channel
    intervalLo = soundIntervalLo + channel
    intervalHi = soundIntervalHi + channel
    osc = soundOsc + channel
    volume = soundVolume + channel

    name = 'sound' + str(channel)
    label(name)

    if channel == 3:
        nop()#ld(0)                           #       199
        ld([videoSync_hSync], OUT)      #       0
        nop()#st([soundOut])                  #       1
        ld('sound' + str(nextChannel))  #       2
        st([nextSound])                 #       3
    else:
        ld('sound' + str(nextChannel))  # 199
        ld([videoSync_hSync], OUT)      # 0
        st([nextSound])                 # 1
    ld([timerHi])                       # 2     4
    bne(name + '.skip')                 # 3     5
    ld([timerLo])                       # 4     6
    adda([intervalLo])                  # 5     7
    st([timerLo])                       # 6     8
    anda(0x80)                          # 7     9
    beq(pc() + 3)                       # 8     10
    bra(pc() + 3)                       # 9     11
    ld(0)                               # 10    12
    ld(-1)                              # 10(!) 12(!)
    adda([intervalHi])                  # 11    13
    st([timerHi])                       # 12    14
    ld([osc])                           # 13    15
    xora(0xF0)                            # 14    16
    bra(name + '.join')                 # 15    17
    st([osc])                           # 16    18
    label(name + '.skip')
    ld([timerHi])                       # 5     7
    suba(1)                             # 6     8
    st([timerHi])                       # 7     9
    ld([timerLo])                       # 8     10
    anda(0x7F)                          # 9     11
    st([timerLo])                       # 10    12
    wait(5)                             # 11 12 13 14 15     13 14 15 16 17
    ld([osc])                      # 16    18
    label(name + '.join')
    anda([volume])                      # 17    19


    if channel == 0:
        st([soundOut])
        nop()
        nop()
        bra([nextVideo])
        ld([xout])
    elif channel == 3:
        adda([soundOut])                    # 18    20
        bra([nextVideo])                # 21
        st([xout])                      # 22
    else:
        adda([soundOut])                    # 18    20
        st([soundOut])                  # 19
        nop()                           # 20
        bra([nextVideo])                # 21
        ld([xout])                      # 22

label('oscillators')
oscillator(0, 1)
oscillator(1, 2)
oscillator(2, 3)
oscillator(3, 0)

def visibleLine(index, nextIndex):
    name = 'visible' + str(index)
    label(name)

    nop()                               # 23
    ld([videoSync_idle], OUT)           # 24
    ld('visible' + str(nextIndex))      # 25
    st([nextVideo])                     # 26
    wait(4)                             # 27 28 29 30
    bra('pixels')                       # 31
    nop()                               # 32

visibleLine(1, 2)
visibleLine(2, 3)
visibleLine(3, 4)

# Blank visible line
label('visible4')
nop()                                   # 23
ld([videoSync_idle], OUT)               # 24
ld([videoLine])                         # 25
for i in range(4):
    nop()                               # 26 27 28 29
adda(1)                                 # 30
st([videoLine])                         # 31
xora(120)                               # 32
bne('visible4.else')                    # 33
ld('vFront')                            # 34
st([nextVideo])                         # 35
ld(vFrontTime)                          # 36
ld([nextCodeHi], Y)                     # 37
jmp(Y, [nextCodeLo])                    # 38
st([videoLine])                         # 39
label('visible4.else')
ld('visible1')                          # 35
st([nextVideo])                         # 36
ld([nextCodeHi], Y)                     # 37
jmp(Y, [nextCodeLo])                    # 38
nop()                                   # 39

label('vFront')
nop()                                   # 23
ld([videoSync_idle], OUT)               # 24
ld([videoLine])                         # 25
for i in range(4):
    nop()                               # 26 27 28 29
suba(1)                                 # 30
bne('vFront.skip')                      # 31
st([videoLine])                         # 32
ld('vSync')                             # 33
st([nextVideo])                         # 34
ld(vSyncTime)                           # 35
st([videoLine])                         # 36
ld([nextCodeHi], Y)                     # 37
jmp(Y, [nextCodeLo])                    # 38
nop()                                   # 39
label('vFront.skip')
wait(4)                                 # 33 34 35 36
ld([nextCodeHi], Y)                     # 37
jmp(Y, [nextCodeLo])                    # 38
# 39 is first nop of vSync

def blankSyncedLine(name, nextName, nextTime, syncH, syncI):
    label(name)
    nop()                               # 23
    ld(syncI, OUT)                      # 24
    ld([videoLine])                     # 25
    suba(1)                             # 26
    bne(name + '.skip')                 # 27
    st([videoLine])                     # 28
    ld(nextName)                        # 29
    st([nextVideo])                     # 30
    ld(nextTime)                        # 31
    st([videoLine])                     # 32
    label(name + '.join')
    ld(syncH)                           # 33
    st([videoSync_hSync])               # 34
    ld(syncI)                           # 35
    st([videoSync_idle])                # 36
    ld([nextCodeHi], Y)                 # 37
    jmp(Y, [nextCodeLo])                # 38
    nop()                               # 39
    label(name + '.skip')
    wait(2)                             # 29 30
    bra(name + '.join')                 # 31                              # 32

blankSyncedLine('vSync', 'vBack', vBackTime, 0, syncBits ^ vSync)
blankSyncedLine('vBack', 'visible1', 1, syncBits ^ hSync, syncBits)

print(lo(pc()))

# Bring pixels to the end of the page
while lo(pc()) != 255:
    nop()

# Execution should be returned to the video loop after 156 cycles of code
def returnToVideo():
    ld(hi('oscillators'), Y)            # 196
    jmp(Y, [nextSound])                 # 197
    nop()                               # 198

label('pixels')
ld([videoLine], Y)                      # 33
ld([videoScroll], X)                    # 34
ld(syncBits)                            # 35
for i in range(160):
    ora([Y, Xpp], OUT)                  # 36 - 195
returnToVideo()

# ROM page 3: Code
align(0x100, 0x100)

# Waits until next frame
label('idle')
ld([nextVideo])        # 1
suba('vFront')         # 2
bne('idle.else1')      # 3
ld([videoLine])        # 4
suba(vFrontTime)       # 5
bne('idle.else2')      # 6
ld('perFrame')         # 7
bra('idle.join')       # 8
st([nextCodeLo])       # 9
label('idle.else1')
wait(3)                # 5 6 7
label('idle.else2')
wait(2)                # 8 9
label('idle.join')
# 10
wait(156 - 9)                               # 40 - 195
returnToVideo()

# Run every frame
label('perFrame')
ld([videoScroll])
adda(1)
st([videoScroll])
ld(4)
st([musicChannel])
ld(hi('musicTick'))
st([nextCodeHi])
ld('musicTick')
st([nextCodeLo])
wait(156 - 3 - 6)
returnToVideo()

# Clears the screen
# Set index to 120 before running
label('clearScreen')
ld([index])                            # 1
adda(7, Y)                             # 2
ld(0, X)                               # 3
for i in range(80):                    #
    st(0b00010101, [Y, Xpp])           # 4 - 83
ld([index])                            # 84
suba(1)                                # 85
bne('clearScreen.continue')            # 86
st([index])                            # 87
ld('idle')                             # 88
st([nextCodeLo])                       # 89
wait(156 - 89)                         # 90...
returnToVideo()
label('clearScreen.continue')
wait(156 - 87)                         # 88...
returnToVideo()

align(0x100, 0x100)

label('musicTick')
ld([musicChannel], Y)                # 1
ld([Y, musicTimer])                  # 2
bne('musicTick.skip')                # 3
ld([Y, musicPointerLo])              # 4
ld(AC, X)                            # 5
adda(1)                              # 6
st([Y, musicPointerLo])              # 7
ld([Y, musicPointerHi])              # 8
ld(AC, Y)                            # 9
ld([Y, X])                           # 10
st([musicInstruction])               # 11
anda(0x80)                           # 12
beq('musicTick.duration')            # 13

ld([musicChannel])                   # 14
adda(soundIntervalHi - 1, X)         # 15
ld([musicInstruction])               # 16
anda(0x7F)                           # 17
adda(AC)                             # 18
adda('musicNoteLookup')              # 19
st([musicInstruction])               # 20
bra(AC)                              # 21
bra(pc() + 1)                        # 23(!)
st([X])                              # 24
ld([musicChannel])                   # 25
adda(soundIntervalLo - 1, X)         # 26 Subtract 1 so channel 1 corresponds to sound 0
ld([musicInstruction])               # 27
adda(1)                              # 28
bra(AC)                              # 29
bra(pc() + 1)                        # 31(!)
st([X])                              # 32
ld([musicChannel], Y)                # 33
ld([Y, musicDuration])               # 34
bra('musicTick.join')                # 35
st([Y, musicTimer])                  # 36
                                     #
label('musicTick.duration')          #
ld([musicInstruction])               # 15
adda('musicDurationLookup')          # 16
bra(AC)                              # 17
bra(pc() + 1)                        # 19(!)
ld([musicChannel], Y)                # 20
st([Y, musicDuration])               # 21
wait(15)                             # 22-36
                                     #
label('musicTick.join')              #
wait(156 - 36)                       # 37...
returnToVideo()                      #
                                     #
label('musicTick.skip')              #
ld([Y, musicTimer])                  # 5
suba(1)                              # 6
st([Y, musicTimer])                  # 7
ld([musicChannel])                   # 8
suba(1)                              # 9
bne('musicTick.skip.end')            # 10
st([musicChannel])                   # 11
ld(hi('idle'))                       # 12
st([nextCodeHi])                     # 13
ld('idle')                           # 14
st([nextCodeLo])                     # 15
wait(156 - 15)                       # 16...
returnToVideo()
label('musicTick.skip.end')
wait(156 - 11)                       # 12...
returnToVideo()

label('musicNoteLookup') # 18, 24
noteLookupBegin = lo(pc())

def defineNote(freq):
    value = (lo(pc()) - noteLookupBegin) // 2
    ld(calcTimerHi(freq))
    ld(calcTimerLo(freq))
    return value

REST = 0
ld(0)
ld(0)
C2  = defineNote(65.41)
Cs2 = defineNote(69.30)
D2  = defineNote(73.42)
Ds2 = defineNote(73.42)
E2  = defineNote(82.41)
F2  = defineNote(87.31)
Fs2 = defineNote(92.50)
G2  = defineNote(98.00)
Gs2 = defineNote(103.83)
As2 = defineNote(116.54)
B2  = defineNote(123.47)
Cs3 = defineNote(138.59)
Ds3 = defineNote(155.56)
E3  = defineNote(164.81)
F3  = defineNote(174.61)
Fs3 = defineNote(185.00)
G3  = defineNote(196.00)
Gs3 = defineNote(207.65)
As3 = defineNote(233.08)
B3  = defineNote(246.94)
C4  = defineNote(261.63)
Cs4 = defineNote(277.18)
Ds4 = defineNote(311.13)
F4  = defineNote(349.23)
Fs4 = defineNote(369.99)
Gs4 = defineNote(415.30)
As4 = defineNote(466.16)
B4  = defineNote(493.88)
C5  = defineNote(523.25)
Cs5 = defineNote(554.37)
Ds5 = defineNote(622.25)
E5  = defineNote(659.25)
F5  = defineNote(698.46)
Fs5 = defineNote(739.99)
Gs5 = defineNote(830.61)
As5 = defineNote(932.33)
Cs6 = defineNote(1108.73)

label('musicDurationLookup') # 15
ld(15) # 1/8 note
DUR_1_8 = 0
ld(30) # 1/4 note
DUR_1_4 = 1
ld(45)
DUR_3_8 = 2
ld(60)
DUR_1_2 = 3
ld(75)
DUR_5_8 = 4
ld(90) # 3/4 note
DUR_3_4 = 5
ld(105)
DUR_7_8 = 6
ld(150)
DUR_5_4 = 7

def dur(index):
    st(index, [Y, Xpp])

def note(index):
    st(0b10000000 | index, [Y, Xpp])

align(0x100, 0x200)
label('loadMusic')
ld(1, Y)
ld(0, X)

dur(DUR_1_8) # 1/8
note(Fs5)
note(F5)
note(Ds5)
note(Cs5)
note(Ds5)
note(As4)
note(C5)
note(REST)
note(Gs4)
note(REST)
note(Ds5)
note(F5)
note(Fs5)
note(Ds3)
note(Gs5)
note(REST)
note(Cs6)
note(REST)
dur(DUR_3_4) # 3/4
note(As5)
dur(DUR_1_8) # 1/8
note(Fs5)
note(F5)
note(Ds5)
note(Cs5)
note(Ds5)
note(As4)
note(C5)
note(REST)
note(Gs4)
note(REST)
note(Ds4)
dur(DUR_1_8)
note(F4)
note(Fs4)
note(REST)
note(F4)
note(REST)
note(Cs4)
note(REST)
dur(DUR_3_4)
note(Ds4)
dur(DUR_1_8) # 1/8
note(Fs5)
note(F5)
note(Ds5)
note(Cs5)
note(Ds5)
note(As4)
note(C5)
note(REST)
note(Gs4)
note(REST)
note(Ds5)
note(F5)
note(Fs5)
note(Ds3)
note(Gs5)
note(REST)
note(Cs6)
note(REST)
dur(DUR_3_4) # 3/4
note(As5)
dur(DUR_1_8) # 1/8
note(Fs5)
note(F5)
note(Ds5)
note(Cs5)
note(Ds5)
note(As4)
note(C5)
note(REST)
note(Gs4)
note(REST)
note(Ds4)
dur(DUR_1_8)
note(F4)
note(Fs4)
note(REST)
note(F4)
note(REST)
note(Cs4)
note(REST)
dur(DUR_3_4)
note(Ds4)
dur(DUR_1_8)
note(Gs5)
note(Fs5)
note(E5)
note(Ds5)
note(Cs5)
note(E5)
note(Ds5)
note(REST)
note(As4)
note(REST)
note(As4)
note(Ds5)
note(Gs5)
note(Fs5)
note(E5)
note(Ds5)
note(Cs5)
note(E5)
dur(DUR_1_2)
note(Ds5)

ld(2, Y)
ld(0, X)

dur(DUR_1_8)
note(REST)
note(Ds3)
note(Fs3)
note(Gs3)
note(As3)
note(Fs3)
note(Ds4)
note(Gs3)
note(C4)
note(Ds4)
note(C4)
note(Gs3)
dur(DUR_1_4)
note(Ds4)
dur(DUR_1_8)
note(F4)
note(Fs3)
dur(DUR_1_4)
note(C4)
dur(DUR_1_8)
note(Fs3)
note(F3)
note(Ds3)
note(Cs3)
note(Ds3)
note(REST)
note(REST)
note(Ds3)
note(Fs3)
note(Gs3)
note(As3)
note(Fs3)
note(Ds4)
note(Gs3)
note(C4)
note(REST)
note(Ds3)
note(G3)
dur(DUR_1_4)
note(Fs3)
dur(DUR_1_8)
note(Gs3)
note(As3)
note(F3)
note(Cs3)
note(REST)
note(E3)
note(Ds3)
note(Cs3)
note(Ds3)
note(F3)
note(REST)
note(Ds3)
note(Fs3)
note(Gs3)
note(As3)
note(Fs3)
note(Ds4)
note(Gs3)
note(C4)
note(Ds4)
note(C4)
note(Gs3)
dur(DUR_1_4)
note(Ds4)
dur(DUR_1_8)
note(F4)
note(Fs3)
dur(DUR_1_4)
note(C4)
dur(DUR_1_8)
note(Fs3)
note(F3)
note(Ds3)
note(Cs3)
note(Ds3)
note(REST)
note(REST)
note(Ds3)
note(Fs3)
note(Gs3)
note(As3)
note(Fs3)
note(Ds4)
note(Gs3)
note(C4)
note(REST)
note(Ds3)
note(G3)
dur(DUR_1_4)
note(Fs3)
dur(DUR_1_8)
note(Gs3)
note(As3)
note(F3)
note(Cs3)
note(REST)
note(E3)
note(Ds3)
note(Cs3)
note(Ds3)
note(F3)
note(B3)
note(B3)
note(Gs3)
note(Fs3)
note(As3)
note(Gs3)
note(Fs3)
note(Gs3)
note(Ds3)
note(F3)
dur(DUR_1_4)
note(As3)
note(B3)
dur(DUR_1_8)
note(Gs3)
note(Fs3)
note(As3)
note(Gs3)
dur(DUR_1_2)
note(As3)

ld(3, Y)
ld(0, X)

dur(DUR_1_8)
note(Ds2)
note(Ds2)
note(D2)
note(Cs2)
dur(DUR_1_4)
note(Fs2)
dur(DUR_3_4)
note(Gs2)
dur(DUR_1_8)
note(B2)
note(B2)
note(Cs2)
note(C2)
note(F2)
note(F2)
note(Ds2)
note(F2)
note(Ds2)
note(D2)
note(Gs2)
note(As2)
note(Ds2)
note(Ds2)
note(D2)
note(Cs2)
dur(DUR_1_4)
note(Fs2)
dur(DUR_5_8)
note(Gs2)
dur(DUR_1_8)
note(G2)
dur(DUR_1_4)
note(B2)
note(Cs2)
dur(DUR_3_8)
note(Gs2)
dur(DUR_1_8)
note(REST)
note(REST)
note(Cs2)
note(REST)
note(REST)
dur(DUR_1_8)
note(Ds2)
note(Ds2)
note(D2)
note(Cs2)
dur(DUR_1_4)
note(Fs2)
dur(DUR_3_4)
note(Gs2)
dur(DUR_1_8)
note(B2)
note(B2)
note(Cs2)
note(C2)
note(F2)
note(F2)
note(Ds2)
note(F2)
note(Ds2)
note(D2)
note(Gs2)
note(As2)
note(Ds2)
note(Ds2)
note(D2)
note(Cs2)
dur(DUR_1_4)
note(Fs2)
dur(DUR_5_8)
note(Gs2)
dur(DUR_1_8)
note(G2)
dur(DUR_1_4)
note(B2)
note(Cs2)
dur(DUR_3_8)
note(Gs2)
dur(DUR_1_8)
note(REST)
note(REST)
note(Cs2)
note(As2)
note(As2)
note(E2)
note(B2)
note(Gs2)
note(C2)
note(Fs2)
note(F2)
dur(DUR_3_4)
note(Ds2)
dur(DUR_1_8)
note(E2)
note(E2)
note(D2)
note(C2)
note(Ds2)
note(Cs2)
dur(DUR_1_2)
note(Ds2)

ld(4, Y)
ld(0, X)
dur(DUR_1_4)
note(REST); note(REST)
note(Cs4)
note(REST); note(REST)
note(Ds3)
note(Fs3)
dur(DUR_1_8)
note(F3)
note(REST)
note(Gs3)
note(F3)
dur(DUR_5_4)
note(REST)
dur(DUR_1_4)
note(Cs4)
dur(DUR_7_8)
note(REST)
dur(DUR_1_8)
note(Ds3)
dur(DUR_1_2)
note(REST)
dur(DUR_3_8)
note(Ds2)
dur(DUR_1_8)
note(REST)
note(As2)
note(As2)
dur(DUR_1_4)
note(REST); note(REST)
note(Cs4)
note(REST); note(REST)
note(Ds3)
note(Fs3)
dur(DUR_1_8)
note(F3)
note(REST)
note(Gs3)
note(F3)
dur(DUR_5_4)
note(REST)
dur(DUR_1_4)
note(Cs4)
dur(DUR_7_8)
note(REST)
dur(DUR_1_8)
note(Ds3)
dur(DUR_1_2)
note(REST)
dur(DUR_3_8)
note(Ds2)
dur(DUR_1_8)
note(REST)
note(As2)
note(As2)
note(E5)
note(Ds5)
note(Cs5)
note(B4)
note(As4)
note(B4)
note(As4)
note(REST)
note(Fs4)
note(REST)
note(Ds3)
note(Ds3)
note(E5)
note(Ds5)
note(Cs5)
note(B4)
note(As4)
note(B4)
dur(DUR_1_2)
note(As4)

ld(hi('loadMusic_return'), Y)
jmp(Y, 'loadMusic_return')
nop()

end()
writeRomFiles('sound')