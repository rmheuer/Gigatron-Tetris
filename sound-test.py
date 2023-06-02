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

leds = zpByte()
xout = zpByte()

oscNext = zpByte()
oscMix = zpByte()
oscTimerLo = zpByte(4)
oscTimerHi = zpByte(4)
oscIntervalLo = zpByte(4)
oscIntervalHi = zpByte(4)
oscOut = zpByte(4)
oscVolume = zpByte(4)

nextVideo = zpByte()
videoLine = zpByte()
videoSync_idle = zpByte()
videoSync_hSync = zpByte()

nextCodeLo = zpByte()
nextCodeHi = zpByte()

loopIdx = zpByte()
temp = zpByte()

musicPtrLo = 255
musicPtrHi = 254
musicDurLo = 253
musicDurHi = 252
musicTimerLo = 251
musicTimerHi = 250

SAMPLE_RATE = 525 * 60 / 4.0
def calcTickInterval(freq):
    return round(SAMPLE_RATE / (2 * freq) * 128) / 128.0

def calcTimerHi(freq):
    ticks = math.floor(calcTickInterval(freq)) - 1
    if ticks < 0:
        raise Exception("Frequency too high: " + str(freq))
    return ticks

def calcTimerLo(freq):
    return int((calcTickInterval(freq) % 1) * 128)

# Page 0: Initialization
align(0x100, 0x100)

# Initialize shift-down lookup
ld(0)
st([0])
ld(1)
st([0x80])

# Initialize video loop
ld('visible0')
st([nextVideo])
ld(1)
st([videoLine])
ld(syncBits ^ hSync)
st([videoSync_hSync])
ld(syncBits)
st([videoSync_idle])

# Initialize oscillators and audio loop
ld('osc0')
st([oscNext])
pitches = [65.41, 329.63, 392, 523.25]
for i in range(4):
    ld(127)
    st([oscTimerHi + i])
    st([oscTimerLo + i])

    pitch = pitches[i]
    interval_lo = calcTimerLo(pitch)
    interval_hi = calcTimerHi(pitch)
    print(pitch, "Hz: Hi", interval_hi, "Lo", interval_lo)

    ld(interval_hi)
    st([oscIntervalHi + i])
    ld(interval_lo)
    st([oscIntervalLo + i])
    ld(0)
    st([oscOut + i])
    ld(3 << 4)
    st([oscVolume + i])

# Initialize code
ld('idle')
st([nextCodeLo])
ld(hi('idle'))
st([nextCodeHi])

ld(0b1010)
st([leds])

# Enter main loop
ld(hi('oscillators'), Y)
jmp(Y, [oscNext])
nop()

# Pages 1 and 2: Audio & Video
align(0x100, 0x200)

def oscillator(channel, nextChannel):
    timerLo = oscTimerLo + channel
    timerHi = oscTimerHi + channel
    intervalLo = oscIntervalLo + channel
    intervalHi = oscIntervalHi + channel
    out = oscOut + channel
    volume = oscVolume + channel

    name = 'osc' + str(channel)
    label(name)

    ld([videoSync_hSync], OUT)     # 0 [hSync falls]
    ld([timerHi])                  # 1
    bne(name + '.skip')            # 2
    ld([timerLo])                  # 3
    adda([intervalLo])             # 4
    anda(0x80, X)                  # 5
    anda(0x7F)                     # 6
    st([timerLo])                  # 7
    ld([intervalHi])               # 8
    adda([X])                      # 9
    st([timerHi])                  # 10
    ld([out])                      # 11
    xora(0xF0)                     # 12
    bra(name + '.join')            # 13
    st([out])                      # 14

    label(name + '.skip')
    ld([timerHi])                  # 4
    suba(1)                        # 5
    st([timerHi])                  # 6
    wait(7)                        # 7 8 9 10 11 12 13
    ld([out])                      # 14

    label(name + '.join')
    anda([volume])                 # 15
    if channel == 0:
        ora([leds])                # 16
        st([oscMix])               # 17
    elif channel == 1 or channel == 2:
        adda([oscMix])             # 16
        st([oscMix])               # 17
    elif channel == 3:
        adda([oscMix])             # 16
        st([xout])                 # 17

    ld('osc' + str(nextChannel))   # 18
    bra([nextVideo])               # 19
    st([oscNext])                  # 20
    
label('oscillators')
oscillator(0, 1)
oscillator(1, 2)
oscillator(2, 3)
oscillator(3, 0)

def visibleLine(index, nextIndex):
    label('visible' + str(index))
    ld('visible' + str(nextIndex)) # 21
    st([nextVideo])                # 22
    ld([xout])                     # 23
    ld([videoSync_idle], OUT)      # 24 [hSync rises]
    wait(6)                        # 25 26 27 28 29 30
    bra('pixels')                  # 31
    nop()                          # 32

visibleLine(0, 1)
visibleLine(1, 2)
visibleLine(2, 3)

# Blank visible line
label('visible3')
nop()                              # 21
ld([nextCodeHi], Y)                # 22
ld([xout])                         # 23
ld([videoSync_idle], OUT)          # 24 [hSync rises]
ld([videoLine])                    # 25
adda(1)                            # 26
st([videoLine])                    # 27
xora(120 + 1)                      # 28
bne('visible3.else')               # 29
ld('vFrontFirst')                  # 30
st([nextVideo])                    # 31
ld(vFrontTime - 2)                 # 32
jmp(Y, [nextCodeLo])               # 33
st([videoLine])                    # 34
label('visible3.else')
ld('visible0')                     # 31
st([nextVideo])                    # 32
jmp(Y, [nextCodeLo])               # 33
nop()                              # 34

# First line of vFront, calls perFrame
label('vFrontFirst')
nop()                              # 21
ld(hi('perFrame'), Y)              # 22
ld([xout])                         # 23
ld([videoSync_idle], OUT)          # 24 [hSync rises]
ld('vFront')                       # 25
jmp(Y, 'perFrame')                 # 26
st([nextVideo])                    # 27

label('vFront')
ld([nextCodeHi], Y)                # 21
nop()                              # 22
ld([xout])                         # 23
ld([videoSync_idle], OUT)          # 24 [hSync rises]
ld([videoLine])                    # 25
bne('vFront.skip')                 # 26
suba(1)                            # 27
ld('vSync')                        # 28
st([nextVideo])                    # 29
ld(vSyncTime - 1)                  # 30
st([videoLine])                    # 31
nop()                              # 32
jmp(Y, [nextCodeLo])               # 33
nop()                              # 34
label('vFront.skip')
st([videoLine])                    # 28
wait(4)                            # 29 30 31 32
jmp(Y, [nextCodeLo])               # 33
nop()                              # 34

def blankSyncedLine(name, nextName, nextTime, syncH, syncI):
    label(name)
    ld(syncH)                      # 21
    st([videoSync_hSync])          # 22
    ld([xout])                     # 23
    ld(syncI, OUT)                 # 24 [hSync rises]
    ld(syncI)                      # 25
    st([videoSync_idle])           # 26
    ld([videoLine])                # 27
    bne(name + '.skip')            # 28
    ld([nextCodeHi], Y)            # 29
    ld(nextName)                   # 30
    st([nextVideo])                # 31
    ld(nextTime)                   # 32
    jmp(Y, [nextCodeLo])           # 33
    st([videoLine])                # 34
    label(name + '.skip')
    suba(1)                        # 30
    st([videoLine])                # 31
    nop()                          # 32
    jmp(Y, [nextCodeLo])           # 33
    nop()                          # 34

blankSyncedLine('vSync', 'vBack', vBackTime - 1, 0, syncBits ^ vSync)
blankSyncedLine('vBack', 'visible0', 1, syncBits ^ hSync, syncBits)

def returnToLoop():
    ld(hi('oscillators'), Y)       # 197
    jmp(Y, [oscNext])              # 198
    nop()                          # 199
    
# Align to end of page
while lo(pc()) != 255:
    nop()

label('pixels')
ld([videoLine], Y)                 # 33
ld(0, X)                           # 34
ld(syncBits)                       # 35
for i in range(160):
    ora([Y, Xpp], OUT)             # 36 - 195
ld([videoSync_idle], OUT)          # 196 [hFront start]
returnToLoop()

# Page 3: Code
align(0x100, 0x100)

label('perFrame')
wait(169) # 28 - 196
returnToLoop()

label('idle')
wait(162) # 35 - 196
returnToLoop()

def musicTick():
    if timerHi != 0:
        timerHi--
        return

    inst = RAM[ptrHi, ptrLo]
    if inst & 0x80 == 0:
        # duration
        durHi = durLookup[inst << 1]
        durLo = durLookup[inst << 1 + 1]
    else:
        inst = inst << 1 # removes top bit
        oscIntervalHi[idx - 1] = noteLookup[inst]
        oscIntervalLo[idx - 1] = noteLookup[inst + 1]
        timerLo += durLo
        timerHi = durHi + (timerLo & 0x80 ? 1 : 0)
        timerLo &= 0x7F

musicInst = temp
        
label('musicTick')
# If time is remaining, continue to next
ld([loopIdx], Y)      # 1
ld([Y, musicTimerHi]) # 2
bne('musicTick.skip') # 3

# Fetch instruction
ld([Y, musicPtrLo])
ld(AC, X)
ld([Y, musicPtrHi])
ld(AC, Y)
ld([X, Y])
st([musicInst])

# Check if duration
anda(0x80)
beq('musicTick.dur')
ld([loopIdx], Y)

# Look up note interval and configure oscillator
ld([loopIdx])
adda(oscIntervalHi - 1, X)
ld([musicInst])
adda(AC)
adda('musicNoteLookup')
st([musicInst])
bra(AC)
bra(pc() + 1)
st([X])

ld([loopIdx])
adda(oscIntervalLo - 1, X)
ld([musicInst])
adda(1)
bra(AC)
bra(pc() + 1)
st([X])

# Start note duration timer
ld([Y, musicTimerLo])
adda([Y, musicDurLo])
anda(0x80, X)
anda(0x7F)
st([Y, musicTimerLo])
ld([Y, musicDurHi])
adda([X])
st([Y, musicTimerHi])

label('musicTick.dur')
ld([musicInst])
adda(AC)
adda('musicDurLookup')
st([musicInst])
bra(AC)
bra(pc() + 1)
st([Y, musicDurHi])
ld([musicInst])
adda(1)
bra(AC)
bra(pc() + 1)
st([Y, musicDurLo])


label('musicNoteLookup')

label('musicDurLookup')

end()
writeRomFiles('main')
