#include "DesktopTiles.h"
#include <vector>
#include <cassert>
#include <iostream>
int main(){
 std::vector<uint8_t> pixels(320*176*2,0x33);uint16_t x=0,y=0;
 std::vector<uint8_t> frame={'T','D','T','2',64,0,0,0,1,0,0,0,0,0,1,0,1,0,0xf8,0};
 assert(pocketterm::applyDesktopFrame(frame.data(),frame.size(),pixels.data(),pixels.size(),x,y));
 assert(x==64&&y==0&&pixels[0]==0&&pixels[1]==0xf8&&pixels[2]==0x33);
 auto before=pixels;
 frame.pop_back();assert(!pocketterm::applyDesktopFrame(frame.data(),frame.size(),pixels.data(),pixels.size(),x,y));assert(pixels==before);
 frame.push_back(0);frame[10]=0xff;frame[11]=0xff;
 assert(!pocketterm::applyDesktopFrame(frame.data(),frame.size(),pixels.data(),pixels.size(),x,y));assert(pixels==before);
 frame[10]=0;frame[11]=0;frame[8]=61;
 assert(!pocketterm::applyDesktopFrame(frame.data(),frame.size(),pixels.data(),pixels.size(),x,y));
 assert(!pocketterm::applyDesktopFrame(frame.data(),frame.size(),pixels.data(),1,x,y));
 std::cout<<"desktop tile bounds tests: PASS\n";
}
