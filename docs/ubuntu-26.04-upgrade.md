# SM-G955N Ubuntu 26.04 LTS 업그레이드 인수인계

2026-11-25 실기기 기준은 Ubuntu 24.04.5 LTS와
`6.18.0-g955n-usb-r100-vpn2`다. 아래 절차는 26.04 LTS로
옮길 때 사용할 검증 기준이다. 26.04 실기기 검증은 아직 미실행 상태다.
공식 24.04 LTS → 26.04 LTS 경로는 26.04.1부터 열렸다.
[Ubuntu 업그레이드 공지](https://lists.ubuntu.com/archives/ubuntu-announce/2026-September/000328.html)

## 유지할 스피커 수정

- SM-G955N(`dream2lteks`)의 MAX98506 하단 스피커는 UAIF4의
  `GPH3-0`~`GPH3-3`을 사용한다. 네 핀 모두 기능 2와 풀다운을
  사용한다. 삼성 #58에서 앞의 세 핀은 클럭 및 재생 신호가 관측됐고
  네 번째 핀은 앰프의 전압·전류 피드백을 켰을 때만 움직였다.
- 수정 위치는 BOOT에 포함되는
  `arch/arm64/boot/dts/exynos/exynos8895-dream2lteks.dts`의
  `speaker-bus-pins`다. 새 커널이나 BOOT를 빌드할 때 기존
  스피커 DTS 변경 뒤에
  [패치 0138](../patches/proposals/0138-mainline-sm-g955n-speaker-uaif4-pins.patch)을
  적용하고 최종 DTB에서 확인한다. 기존 `GPH0-5`~`GPH0-7` 지정으로
  돌아가면 ALSA 재생 성공과 하단 스피커 무음이 함께 나타날 수 있다.
- Ubuntu Sound 설정의 **Standard** (`HiFi`) 프로필에서
  **Bottom Speaker**가 기본 출력이다. **Voice** 프로필의 수화기,
  **Microphone** 입력은 기존 경로를 사용한다.
  [수정 커밋](https://github.com/TurboCE/galaxy-s8plus-ubuntu/commit/f75c825),
  [실기기 검증](VALIDATION.md#sm-g955n-bottom-speaker-restored-on-gph3)

## 업그레이드 전

1. 정상 부팅되는 GPH3 수정판의 전체 BOOT와 Ubuntu 루트 파일시스템
   (`USERDATA`)을 같은 시점의 복구본으로 따로 보관하고 해시를
   확인한다. TWRP 접근도 확인한다. 커널을 바꿀 경우 새 BOOT와
   `/lib/modules/<커널 릴리스>`를 같은 빌드로 준비한다.
2. 패키지가 관리하지 않는 기기용 ALSA UCM 설정을 보관한다.
   실기기에서 확인한 경로는
   `/usr/share/alsa/ucm2/Samsung/SM-G955N/`과
   `/usr/share/alsa/ucm2/conf.d/g955n-audio/g955n-audio.conf`다.
   사용자 WirePlumber 상태의 `default-profile`, `default-nodes`,
   `default-routes`도 비교용으로 보관한다.
   [UCM 유지보수 기록](../compat/pipewire/README.md)
3. 아래 명령의 결과와 하단 스피커·마이크 동작을 기준으로 남긴다.
   기존 initramfs는 `/etc/hostname`의 `g955n-ubuntu`를 확인한다.

```sh
grep '^PRETTY_NAME=' /etc/os-release
uname -r
cat /etc/hostname
sudo sha256sum /dev/disk/by-partlabel/BOOT
tr '\000' '\n' </proc/device-tree/soc@0/pinctrl@13e60000/speaker-bus-pins/samsung,pins
cat /proc/asound/pcm
wpctl inspect @DEFAULT_AUDIO_SINK@ | grep 'node.name'
wpctl inspect @DEFAULT_AUDIO_SOURCE@ | grep 'node.name'
```

검증된 24.04.5 기준의 전체 BOOT SHA-256은
`66b721877709fb6756fe2c73e852290f61aae96ae33694edadd7b318ef714985`다.
다른 BOOT를 쓰면 새 이미지 해시를 기록한다.

## 업그레이드 및 확인

먼저 복구 가능한 복제본에서 Ubuntu의 정식 LTS 업그레이드 절차를
따른다. BOOT나 커널을 함께 변경해야 할 때는 루트 파일시스템
업그레이드의 효과와 구분할 수 있도록 각각 검증한다.
[Ubuntu Desktop 공식 절차](https://ubuntu.com/desktop/docs/en/26.04/how-to/upgrade-ubuntu-desktop/)

재부팅 후 위 명령을 다시 실행하고 다음 항목을 확인한다.

- 런타임 DT에 `gph3-0`~`gph3-3`가 모두 표시된다. ALSA에서
  하단 스피커 PCM 0, 마이크 PCM 1, 수화기 PCM 2가 등록된다.
- Sound 설정에서 **Standard → Bottom Speaker**와 **Microphone**을
  선택할 수 있다. 일반 데스크톱 앱으로 재생해 하단 스피커에서
  실제 소리가 나는지 듣고, 마이크 녹음을 확인한다. **Voice**에서
  수화기를 확인한 뒤 **Standard**로 돌아와 재부팅하고 기본 출력이
  유지되는지 확인한다.
- DT와 ALSA가 정상인데 Sound에서 장치가 사라졌다면 기기용 UCM
  파일과 WirePlumber 프로필부터 확인한다. 일반 앱과 직접 ALSA
  재생이 모두 무음이면 BOOT와 실행 중인 DT부터 대조한다.
- 장치 전체의 업그레이드 검증에는 GNOME Wayland 터치 로그인과
  화면 키보드, GPU 가속, 화면 끄기·켜기와 절전 복귀, USB·Wi-Fi,
  자동 회전 및 센서도 포함한다.

업그레이드 후 문제가 생겨 이전 상태로 돌아갈 때는 BOOT와
`USERDATA`의 버전을 맞춘다. BOOT 복구만으로 이미 업그레이드된
루트 파일시스템이 되돌아가지는 않는다.
