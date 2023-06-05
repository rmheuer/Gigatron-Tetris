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

leds = zpByte('leds')
xout = zpByte('xout')

oscNext = zpByte('oscNext')
oscMix = zpByte('oscMix')
oscTimerLo = zpByte('oscTimerLo', 4)
oscTimerHi = zpByte('oscTimerHi', 4)
oscIntervalLo = zpByte('oscIntervalLo', 4)
oscIntervalHi = zpByte('oscIntervalHi', 4)
oscOut = zpByte('oscOut', 4)
oscVolume = zpByte('oscVolume', 4)

nextVideo = zpByte('nextVideo')
videoLine = zpByte('videoLine')
videoSync_idle = zpByte('videoSync_idle')
videoSync_hSync = zpByte('videoSync_hSync')

nextCodeLo = zpByte('nextCodeLo')
nextCodeHi = zpByte('nextCodeHi')

loopIdx = zpByte('loopIdx')
temp = zpByte('temp')

musicPtrLo = 255
musicPtrHi = 254
musicDurLo = 253
musicDurHi = 252
musicTimerLo = 251
musicTimerHi = 250

shapesPage = 1
lookdownPage = 2

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
ld('block_clearScreen')
st([nextCodeLo])
ld(hi('block_clearScreen'))
st([nextCodeHi])

ld(0b1010)
st([leds])

# Enter main loop
#ld(hi('oscillators'), Y)
#jmp(Y, [oscNext])
#nop()

# Load lookup tables
ld(hi('initTables'), Y)
jmp(Y, 'initTables')
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
#ld([videoLine])
#suba(1, Y)
ld([videoLine], Y)                 # 33
ld(0, X)                           # 34
ld(syncBits)                       # 35
for i in range(160):
    ora([Y, Xpp], OUT)             # 36 - 195
ld([videoSync_idle], OUT)          # 196 [hFront start]
returnToLoop()

# ---- TETRIS ----

index1 = zpByte('index1')
index2 = zpByte('index2')
retPtr = zpByte('retPtr')

currentPiece = zpByte('currentPiece')
pieceX = zpByte('pieceX')
pieceY = zpByte('pieceY')
flipX = zpByte('flipX')
flipY = zpByte('flipY')
swapAxes = zpByte('swapAxes')

cellX = zpByte('cellX')
cellY = zpByte('cellY')
color = zpByte('color')

kickPage = 1
srcKickTbl = 7 * 4
dstKickTbl = srcKickTbl + 5
kickIndirectionTbl = 64

# Overall flow:
#
# Begin game:
# Clear screen
# Draw grid bounds
# Gen new piece
#
# perFrame:
# drawPiece(background) : Erase current piece graphic
#
# if rotate button rising, try rotate
#
# if left button rising, try move piece left
# if right button rising, try move piece right
#
# if down button pressed, set drop timer rate to fast, else normal
# if down button rising, set drop timer to 0 for immediate drop
# if down timer expires:
#   move piece down
#   if collides:
#     move piece up
#     drawPiece(pieceColor | collision bit)
#     gen new piece
#
# drawPiece(pieceColor) : Draw updated piece graphic

# Page 3: Code
align(0x100, 0x100)

tester = zpByte('tester')
tester2 = zpByte('tester2')

label('perFrame')

ld([tester])
bne('perFrame.noTest')
suba(1)

ld(59)
st([tester])
ld([tester2])
adda(1)
anda(0x3F)
st([tester2])
ld(hi('block_setupRotation'))
st([nextCodeHi])
ld('block_setupRotation')
bra('perFrame.join')
st([nextCodeLo])

label('perFrame.noTest')
st([tester])
ld(hi('idle'))
st([nextCodeHi])
ld('idle')
st([nextCodeLo])
wait(5)

label('perFrame.join')

ld([tester2])
st([color])

wait(169 - 9 - 18) # 28 - 196
returnToLoop()

label('idle')
wait(162) # 35 - 196
returnToLoop()

# Draws a tetromino with its rotation center at (cellX, cellY) with color [color]
# Shape is determined based on [currentPiece]
# Shape is transformed based on [flipX], [flipY], and [swapAxes]
# Takes 4 scanlines
#   Requires [index1] set to 3
label('block_drawPiece')
ld('block_drawPiece.return') # 35
st([retPtr])                 # 36
bra('getCell')               # 37
ld([index1])                 # 38
# getCell: 39...73
label('block_drawPiece.return')
ld([index1])                 # 74
suba(1)                      # 75
st([index1])                 # 76
blt(pc() + 3)                # 77  index1 < 0 ? idle : drawPiece
bra(pc() + 3)                # 78
ld('block_drawPiece')        # 79
ld('idle')                   # 79
st([nextCodeLo])             # 80
wait(55)                     # 81...135
# Fall-through to drawCell

# Draws one 5x5 cell with top-left corner at (cellX, cellY) with color [color]
label('drawCell')
ld(4)                  # 136
label('drawCell.loop')
st([loopIdx])          # 185 173 161 149 137
adda([cellY], Y)       # 186 174 162 150 138
ld([cellX], X)         # 187 175 163 151 139
ld([color])            # 188 176 164 152 140
for i in range(5):
    st([Y, Xpp])       # 189 177 165 153 141
ld([loopIdx])          # 194 182 170 158 146
bne('drawCell.loop')   # 195 183 171 159 147
suba(1)                # 196 184 172 160 148
ld([pieceX])
adda(2, X)
ld([pieceY])
adda(2, Y)
ld(0b111111)
st([Y, X])
returnToLoop()

# Gets the position of the n'th cell of the current piece
# Desired index should be in AC
# Return address should be in [retPtr]
# 35 cycles
offsetX = zpByte('offsetX')
offsetY = zpByte('offsetY')
offset = offsetY
label('getCell')

# Read n'th packed raw offset
adda([currentPiece], X)   # 1
ld(shapesPage, Y)         # 2
ld([Y, X])                # 3
st([offset], X)           # 4  Save in [offset], and load to X for lookdown

# Extract X position using lookdown table
ld(lookdownPage, Y)       # 5
ld([Y, X])                # 6
suba(5)                   # 7  Correct for encoded mino being 1 tile off
st([offsetX])             # 8

# Extract Y position manually
ld([offset])              # 9
anda(7)                   # 10  Mask out bottom 3 bits
suba(1)                   # 11  Account for 1 tile offset
st([offsetY])             # 12
adda(AC)                  # 13  Shift left 2
adda(AC)                  # 14
adda([offsetY])           # 15  Add offset for effective multiply by 5
st([offsetY])             # 16

# Flip X position if needed
ld([flipX])               # 17
beq(pc() + 3)             # 18
bra(pc() + 3)             # 19
ld([offsetX])             # 20  Unflipped if flipX != 0
suba([offsetX])           # 20  Flipped if flipX == 0; sub works as 0 is in AC
st([offsetX])             # 21

# Flip Y position if needed
ld([flipY])               # 22
beq(pc() + 3)             # 23
bra(pc() + 3)             # 24
ld([offsetY])             # 25
suba([offsetY])           # 25
st([offsetY])             # 26

# Calculate absolute position, and swap offsets if needed
ld([swapAxes])            # 27
beq('getCell.noSwap')     # 28
ld([offsetX])             # 29  Shared
adda([pieceY])            # 30
st([cellY])               # 31
ld([offsetY])             # 32
adda([pieceX])            # 33
bra([retPtr])             # 34
st([cellX])               # 35
label('getCell.noSwap')
adda([pieceX])            # 30
st([cellX])               # 31
ld([offsetY])             # 32
adda([pieceY])            # 33
bra([retPtr])             # 34
st([cellY])               # 35

srcOffset = zpByte('srcOffset')
dstOffset = zpByte('dstOffset')
netOffsetX = zpByte('netOffsetX')
netOffsetY = zpByte('netOffsetY')
label('block_tryRotate')
ld([index2])
adda(dstKickTbl, X)
ld(kickPage, Y)
ld([Y, X])
st([dstOffset], X)
ld(lookdownPage, Y)
ld([Y, X])
st([temp]) # Temp has lookupDecode[dstOffset]

ld([index2])
adda(srcKickTbl, X)
ld(kickPage, Y)
ld([Y, X])
st([srcOffset], X)
ld(lookdownPage, Y)
ld([Y, X]) # AC has lookupDecode[srcOffset]

suba([temp])
st([netOffsetX])
adda([pieceX])
st([pieceX])

ld([srcOffset])
anda(7)
st([temp])
ld([dstOffset])
anda(7)
suba([temp]) # dst - src: accounts for kick tables being flipped vertically
st([temp])
adda(AC)
adda(AC)
adda([temp])
st([netOffsetY])
adda([pieceY])
st([pieceY]) # 28 TODO: FIX NUMBERS

collide = zpByte('collide')
ld(0) # 29
st([collide]) # 30

ld('block_tryRotate.checkRet') # 31
st([retPtr]) # 32
ld(1) # 33

label('block_tryRotate.loop')
st([index1])            # 34 81
bra('getCell')          # 35 82
adda(2)                 # 36 83  Offset 0, 1 to 2, 3
# getCell: 37-71 84-118
label('block_tryRotate.checkRet')
ld([cellX], X)          # 72 119
ld([cellY], Y)          # 73 120
ld([Y, X])              # 74 121
anda(128)               # 75 122
ora([collide])          # 76 123
st([collide])           # 77 124
ld([index1])            # 78 125
bne('block_tryRotate.loop') # 79 126
suba(1)                 # 80 127

wait(33)                # 128-160
ld('block_tryRotate2')  # 161
st([nextCodeLo])        # 162
returnToLoop()

# Try rotation part 2
label('block_tryRotate2')
ld('block_tryRotate2.checkRet')     # 1
st([retPtr])                        # 2
ld(1)                               # 3
label('block_tryRotate2.loop')
bra('getCell')                      # 4 50
st([index1])                        # 5 51
#                            getCell: 6-40 52-86
label('block_tryRotate2.checkRet')
ld([cellX], X)                      # 41 87
ld([cellY], Y)                      # 42 88
ld([Y, X])                          # 43 89
anda(128)                           # 44 90
ora([collide])                      # 45 91
st([collide])                       # 46 92
ld([index1])                        # 47 93
bne('block_tryRotate2.loop')        # 48 94
suba(1)                             # 49 95

ld([collide])                             # 96  If collide != 0, it hit something
beq('block_tryRotate2.noCollision')       # 97
ld([index2])                              # 98
bra(pc()) # REMOVE
suba(4)                                   # V 99
bne('block_tryRotate2.collision.retry')   # | 100
# Last attempt failed, no rotation          | |
# CCW rotation                              | |
ld([flipY])                               # | 101
st([temp])                                # | V 102
ld([flipX])                               # | | 103
st([flipY])                               # | | 104
ld(1)                                     # | | 105
suba([temp])                              # | | 106
st([flipX])                               # | | 107
ld(1)                                     # | | 108
suba([swapAxes])                          # | | 109
st([swapAxes])                            # | | 110
ld('test_nextThing')                                # | | 111
bra('block_tryRotate2.collision.join')    # | | 112
st([nextCodeLo])                          # | | 113 >-+
                                          # | |       |
label('block_tryRotate2.collision.retry') # | |       |
# Retry next attempt with next offset       | V       |
ld([index2])                              # | 102     |
adda(1)                                   # | 103     |
st([index2])                              # | 104     |
ld('block_tryRotate')                     # | 105     |
st([nextCodeLo])                          # | 106     |
wait(7)                                   # | 107-113 |
label('block_tryRotate2.collision.join')  # | |       |
                                          # | |       |
ld([pieceX])                              # | 114 <---+
suba([netOffsetX])                        # | 115
st([pieceX])                              # | 116
ld([pieceY])                              # | 117
suba([netOffsetY])                        # | 118
bra('block_tryRotate2.join')              # | 119
st([pieceY])                              # | 120 >-+
                                          # |       |
label('block_tryRotate2.noCollision')     # |       |
# Rotation succeeded, leave piece         # V       |
ld('test_nextThing')                                # 99      |
st([nextCodeLo])                          # 100     |
wait(20)                                  # 101-120 |
label('block_tryRotate2.join')            # |       |
wait(42)                                  # 121-162 <
returnToLoop()

label('test_nextThing')
wait(158)
ld(3)
st([index1])
ld('block_drawPiece')
st([nextCodeLo])
returnToLoop()

align(0x100, 0x100)

label('block_clearScreen')
ld([index1])
adda(7, Y)
ld(0, X)
for i in range(80):
    st(0b00010101, [Y, Xpp])
ld([index1])
suba(1)
bne('block_clearScreen.continue')
st([index1])
ld('idle')
st([nextCodeLo])
ld(hi('idle'))
st([nextCodeLo])
wait(162-91)
returnToLoop()
label('block_clearScreen.continue')
wait(162-87)
returnToLoop()

# Page 4: Code (cont.)
align(0x100, 0x100)

# 19 cycles; 13 cycles local, 6 cycles in load
def fetchKickTable(name, target):
    rotIdx = temp

    # Prepare for destination table jump
    ld('block_setupRotation.ret_' + name)
    st([retPtr])    
    
    # Calculate rotation index
    ld(1)
    suba([flipX])
    adda(AC)
    ora([swapAxes]) # Will result in index 0, 1, 2, 3 clockwise

    # Get destination table address
    ld(lookdownPage, Y)
    ora([currentPiece]) # Combine current piece and rotation index
    adda(kickIndirectionTbl, X)
    ld([Y, X])

    # Fetch source table into target
    ld(kickPage, Y)
    bra(AC)
    ld(target, X)
    label('block_setupRotation.ret_' + name)

label('block_setupRotation')

fetchKickTable('src', srcKickTbl) # 19 Get current kick offsets before rotation

# Rotate clockwise
ld([flipX])
st([temp])
ld([flipY])
st([flipX])
ld(1)
suba([temp])
st([flipY])
ld(1)
suba([swapAxes])
st([swapAxes]) # 29

fetchKickTable('dst', dstKickTbl) # 48 Get current kick offsets after rotation

# TODO: Do rotation attempt sequence instead of immediate draw
ld(0)
st([index2])
ld('block_tryRotate')
st([nextCodeLo])
ld(hi('block_tryRotate'))
st([nextCodeHi])
#ld(3)
#st([index1])
#ld('block_drawPiece')
#st([nextCodeLo])
#ld(hi('block_drawPiece'))
#st([nextCodeHi])

wait(150 - 6) # 48...196
returnToLoop()

# kickPage should be in Y
# Either kickTblSrc or kickTblDst should be in X
# 6 cycles
def kick_tbl(name, *offsets):
    label(name)
    for i in range(len(offsets)):
        offset = offsets[i]
        offX = offset[0]
        offY = offset[1]
        if i == len(offsets) - 1:
            bra([retPtr])
        st(((offX + 2) << 3) | (offY + 2), [Y, Xpp])

# TODO: Reuse duplicate rows (space optimization)
kick_tbl('kick_jlstz_0', (0, 0), ( 0, 0), ( 0,  0), (0, 0), ( 0, 0))
kick_tbl('kick_jlstz_1', (0, 0), ( 1, 0), ( 1, -1), (0, 2), ( 1, 2))
kick_tbl('kick_jlstz_2', (0, 0), ( 0, 0), ( 0,  0), (0, 0), ( 0, 0))
kick_tbl('kick_jlstz_3', (0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2))

kick_tbl('kick_i_0', ( 0, 0), (-1, 0), ( 2, 0), (-1,  0), ( 2,  0))
kick_tbl('kick_i_1', (-1, 0), ( 0, 0), ( 0, 0), ( 0,  1), ( 0, -2))
kick_tbl('kick_i_2', (-1, 1), ( 1, 1), (-2, 1), ( 1,  0), (-2,  0))
kick_tbl('kick_i_3', ( 0, 1), ( 0, 1), ( 0, 1), ( 0, -1), ( 0,  2))

kick_tbl('kick_o_0', ( 0,  0), ( 0,  0), ( 0,  0), ( 0,  0), ( 0,  0))
kick_tbl('kick_o_1', ( 0, -1), ( 0, -1), ( 0, -1), ( 0, -1), ( 0, -1))
kick_tbl('kick_o_2', (-1, -1), (-1, -1), (-1, -1), (-1, -1), (-1, -1))
kick_tbl('kick_o_3', (-1,  0), (-1,  0), (-1,  0), (-1,  0), (-1,  0))

# Page 5: Lookups & initialization
align(0x100, 0x100)
label('initTables')

ld(120)
st([index1])

ld(0)
st([tester2])
ld(60)
st([tester])

ld(20)
st([pieceX])
st([pieceY])

ld(4) # multiplied by 4
st([currentPiece])
ld(1)
st([flipX])
st([flipY])
ld(0)
st([swapAxes])

def mino(x, y):
    st(((x + 1) << 3) | (y + 1), [Y, Xpp])

# MUST stay at X=0
ld(shapesPage, Y)
ld(0, X)
mino(-1,  0); mino( 0,  0); mino(1,  0); mino(2,  0) # I
mino( 0,  0); mino( 1,  0); mino(0, -1); mino(1, -1) # O
mino(-1,  0); mino( 0, -1); mino(0,  0); mino(1,  0) # T
mino(-1, -1); mino(-1,  0); mino(0,  0); mino(1,  0) # J
mino(-1,  0); mino( 0,  0); mino(1, -1); mino(1,  0) # L
mino(-1,  0); mino( 0, -1); mino(0,  0); mino(1, -1) # S
mino(-1, -1); mino( 0, -1); mino(0,  0); mino(1,  0) # Z

# Setup lookdown page
# MUST stay at X=0
ld(lookdownPage, Y)
ld(0, X)
for i in range(8):
    ld(i * 5)
    for j in range(8):
        st([Y, Xpp])

# Setup kick indirection table
# Also on lookdown page, no need for ld(y)
# Lookup index is encoded as currentPiece | rotIdx (currentPiece already shifted up 4)
ld(kickIndirectionTbl, X)
for i in range(4):
    st('kick_i_' + str(i), [Y, Xpp])
for i in range(4):
    st('kick_o_' + str(i), [Y, Xpp])
for i in range(5):
    for i in range(4):
        st('kick_jlstz_' + str(i), [Y, Xpp])

returnToLoop()

end()
writeRomFiles('main')
