from asm import *

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

videoSync_hSync = zpByte()
videoSync_idle = zpByte()

xout = zpByte()
videoTimer = zpByte()
nextVideo = zpByte()

# ROM Page 0: Game initialization
align(0x100, 0x100)
ld(hi('videoLoop'), Y)
jmp(Y, 'videoLoop')
nop()

# ROM Page 1: Video loop
align(0x100, 0x100)
label('videoLoop')

label('hSync')
wait(2)                          #198, 199
ld([videoSync_hSync], OUT)       #0
wait(21) # Sound goes here       #1-21
ld([xout])                       #22
ld([videoTimer])                 #23
ld([videoSync_idle], OUT)        #24
suba(1)                          #25
bra([nextVideo])                 #26
st([videoTimer])                 #27

# AC is guaranteed to contain videoTimer when entering video block

# Sends out one line of pixels
# Switches to frontPorch after 120 lines
# NOTE: if out of space, move the pixel burst out of the page
label('video_visible_start')
adda(1, Y)                       #28
ld('video_visible')              #29
st([nextVideo])                  #30
ld(120)                          #31
bra('video_visible_enter')       #32
st([videoTimer])                 #33
label('video_visible')
adda(1, Y)                       #28
beq(pc() + 3)                    #29
bra(pc() + 3)                    #30
ld('video_frontPorch_enter')     #31
ld('video_visible')              #31(!)
st([nextVideo])                  #32
nop()                            #33
label('video_visible_enter')
ld(0, X)                         #34
ld(syncBits)                     #35
for i in range(160):
    ora([Y, Xpp], OUT)           #36-195
bra('hSync')                     #196
nop()                            #197

label('video_frontPorch_enter')
ld('video_frontPorch')
st([nextVideo])
ld(10)
bra('video_frontPorch_enter')
st([videoTimer])
label('video_frontPorch')

end()
writeRomFiles("tetris")
