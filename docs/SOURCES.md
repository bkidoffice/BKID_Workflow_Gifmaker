# 구현 근거

## 사용자 지정 AutoCrop 프로젝트

- 저장소: https://github.com/bkidoffice/BKID_Workflow_AutoCrop
- 확인 커밋: `1530199024f3c443b75e160efdea9f9a4874f458`
- 읽은 파일: `plugin/README.md`, `AutoCropPlugin.cs`, `CaptureScaleDialog.cs`, `AssemblyInfo.cs`, 두 프로젝트의 csproj/lockfile, `plugin/BKID.AutoCrop.Setup/{Program,ManagedFiles,InstallWorkflow,InstallationVerification}.cs`, `tools/{build_rhi,build_native_toolbar}.py`, `tools/{TestSetup,VerifyPlugin,CheckRhino6}` 소스, 아이콘 SVG/PNG와 WizardImage.
- 사용자의 “우리가 만든 설치 방식·아이콘을 참고” 요청에 따라 같은 BKID 프로젝트 내에서 설치 코드·검증 도구·RUI 생성 구조·잠금 파일을 이식했습니다. 제품명·버전·플러그인 GUID·툴바 GUID namespace·명령·파일 경로를 GIF Maker 전용으로 분리했습니다. 기존 AutoCrop을 지우거나 명령을 덮어쓰지 않습니다.
- 설치 창의 `WizardImage.png`는 기존 원본을 그대로 사용합니다. 아이콘은 기존 파란 코너·은색 큐브를 참조하여 속도선·잔상을 추가한 이미지이며 작은 PNG 및 ICO로 패키징했습니다.
- AutoCrop 저장소의 최상위 라이선스 파일은 발견하지 못했습니다. 사용자 소유 프로젝트에 대한 명시적 적용 요청을 근거로 이식했으며, 제3자에 대한 포괄적인 재배포 허가로 해석하지 않습니다.

## McNeel 공식 API·소스

- https://github.com/mcneel/rhinoscriptsyntax/blob/master/Scripts/rhinoscript/object.py
  - 실제 `CopyObjects`, `TransformObjects`를 읽어 `doc.Objects.Transform(id, transform, deleteOriginal)`의 복사·이동 반환 ID 처리 확인.
  - 소스 복제 없이 호출 원리를 사용했습니다. 저장소 LICENSE는 Robert McNeel & Associates의 MIT 라이선스입니다.
- https://github.com/mcneel/rhino-developer-samples/blob/8/rhinocommon/cs/SampleCsCommands/SampleCsViewCapture.cs
  - `ViewCapture` 크기·그리드·축·배경 설정 → `CaptureToBitmap(view)` 흐름을 확인했습니다. 코드 원문은 배포하지 않습니다.
- RhinoCommon NuGet `6.0.18016.23451` 참조 어셈블리로 `ViewCapture`, `FindId`, `Transform`, `Hide`, `Show`, `Delete`, 선택 복원 및 툴바 생명주기를 컴파일 검증했습니다.

GIF89a 인코더는 이 프로젝트에서 구현했습니다. 프레임별 적응형 팔레트(기존 고정 팔레트 경로도 유지), 9-bit LZW 사전의 조기 초기화, NETSCAPE 반복 확장을 사용합니다. Pillow는 개발 테스트에서 결과 GIF를 독립적으로 디코딩하는 용도로만 사용하며 플러그인에 배포하지 않습니다.

1.0.1: 원본 AutoCrop SVG를 `assets/AutoCrop_Reference.svg`로 보존하고 파란 프레임 path를 그대로 사용한 벡터 아이콘으로 정규화했습니다. 동일한 CairoSVG 렌더링에서 16·24·32·64px의 모든 프레임 픽셀을 비교했습니다. 속도선 역시 `#0645F5`를 사용합니다. GIF Maker 소유 툴바의 단일 이미지 스트립만 한 번 갱신하며 저장된 도킹·표시 상태와 나머지 XML을 유지합니다.

1.1.0: `motion_preview.py`는 Eto `Dialog<bool>`, `ImageView`, 가로 `Slider`, `UITimer`로 미리보기·타임라인을 구성합니다. 설치된 RhinoCommon 6.0.18016.23451 패키지의 Eto.xml에서 Bitmap(Stream), Slider.Orientation, UITimer, Dialog 이벤트를 확인하고 `tools/CheckRhino6/PreviewApi.cs`로 컴파일 검증했습니다. 실제 Windows Eto UI 실행은 미검증입니다.

1.2.0: AutoCrop 최신 커밋 `781b0a28c9d697e4c83cd8552d2488106445daed`의 실제 RUI와 생성 스크립트를 비교했습니다. 16/24/32px 크기·DPI·표시 방식·컨테이너 기본값이 같습니다. 색 유사도 제거 대신 Rhino ViewCapture 알파 → BGRA → 예약 투명 인덱스를 사용합니다. GIF GCE 투명 플래그와 disposal=2를 적용하고 Pillow 독립 디코딩으로 흰색/검은색·투명 배경·잔상 방지를 검증했습니다.

1.2.1: AutoCrop `capture_dimensions`/`capture`가 1배율에서 `ActiveViewport.Size.Width/Height`를 ViewCapture에 넘기는 것을 확인하고 GIF 기본 출력에도 같은 기준을 적용했습니다. 고정 800px·1600px 제한을 제거했고 1920×1080 기본값의 실제 GIF 크기를 모의 Rhino 통합 테스트로 검증했습니다.

1.3.0: AutoCrop의 `capture()` 실제 호출 흐름과 동일한 ViewCapture 설정으로 원본 PNG 프레임을 먼저 저장하고, `quantize_png` → 자체 `AdaptivePalette.Quantize` → 프레임별 GIF local color table로 합성합니다. C# 코드의 가중 중앙값 분할·오차 확산은 이 프로젝트에서 구현했으며 외부 라이브러리 코드를 복제하지 않았습니다. `tools/TestPalette`는 배포 소스 파일을 직접 링크해 실제 알고리즘을 실행합니다. Rhino 6 SDK의 `RhinoCommon.XML`에서 StatusBar.ShowProgressMeter/UpdateProgressMeter/HideProgressMeter, SetMessagePane 및 ClearMessagePane를 확인하고 컴파일했습니다.

1.4.0: 사용자가 저장된 GIF에서만 면 표현이 깨진다고 확인해 캡처 경로 변경 시도는 배포 전에 제외했습니다. 기존 정상 PNG는 유지하고 자체 `AdaptivePalette`/`gif_writer`를 실행·패키지에서 제외했습니다. FFmpeg의 `palettegen=stats_mode=full:reserve_transparent=1`과 `paletteuse=dither=none:alpha_threshold=128`으로 모든 PNG에 공통 팔레트를 적용합니다. 실제 FFmpeg GIF를 Pillow로 다시 열어 색상·투명도·시간·잔상·이동 중 동일 표면 표현을 검증했습니다. Linux 검증용 FFmpeg는 7.1.5, Windows 동봉본은 8.1.3 계열이며 동봉본의 Windows 실행 자체는 미검증입니다. 배포 출처/고정 해시/소스·라이선스는 `third_party/ffmpeg`에 기록했습니다.

1.5.0: McNeel 공식 샘플 커밋 `8462fc3487f8b7a58595ef73f6a5c09f92717f60`의 `rhinocommon/snippets/from_rhinocommon/cs/ex_gumball.cs`, `rhinocommon/cs/SampleCsCommands/SampleCsGumballCylinder.cs`, `License.md`를 읽었습니다. PickContext→PickGumball→UpdateGumball→GetTransform의 shaded display feedback 흐름을 Datum 좌표계·translation-only 조작으로 적용했습니다. `third_party/mcneel/License.md`에 원문 사용 허가/저작권 고지를 보존하고 설치 패키지에도 포함합니다. Rhino 6 SDK로 실제 조작 코드를 컴파일하고 `TestDatum`은 배포 좌표 변환 소스 파일을 직접 링크합니다.

1.6.0: Rhino 6 SDK의 GetObject.GetMultiple, AcceptNothing, EnablePreSelect 및 SetCustomGeometryFilter로 다음 파트 선택을 구현했습니다. Enter 완료와 Esc 취소를 구분하고, 이미 등록한 임시 파트 ID를 필터로 제외합니다. 자체 `motion_sequence.py`가 단계별 시간→각 파트 진행률을 계산하고 모든 단계의 경계 캡처를 보장합니다. 두 파트의 순차 자세·뒤로 탐색·선택/Datum 취소 후 복원을 모의 Rhino 문서와 실제 FFmpeg 출력으로 검증했습니다.

1.7.0: 기존 McNeel Gumball 흐름에서 TranslateX/Y/Z와 RotateX/Y/Z를 선택한 기능에 맞게 전환합니다. 회전 링의 기준/현재 평면 축으로 atan2 각도를 계산하고 자체 RotationTracker가 ±π 경계를 풀어 회전 수·방향을 기록합니다. 회전 재생은 RhinoCommon Transform.Rotation(angle, axis, DatumOrigin)을 실제 드래그 순서로 합성하고 이전 자세 역변환으로 탐색합니다. 배포 소스의 각도 추적·좌표 변환 테스트와 실제 GIF 생성 통합 테스트를 실행하고 초기 Rhino 6 SDK로 컴파일했습니다.

1.8.0: Rhino GetNumber/회전축 GetOption으로 상단 명령창 각도 입력을 추가하고, Eto NumericStepper의 ValueChanged로 미리보기 상단 각도를 편집합니다. SceneSequence가 이전 자세를 제거한 뒤 새 각도·후속 로컬 축을 재계산하고 완료 자세를 갱신합니다. 실제 GIF 생성 통합 테스트와 기존 SDK 컴파일 검사에 포함했습니다.

1.9.0: Datum Both는 기존 이동·회전 설정을 공통 최초 Datum으로 수집하고 `T(progress) * R(progress)`를 적용해 회전과 이동을 동시에 재생합니다. 이전 자세 역변환 순서는 `R(previous)^-1 * T(previous)^-1`입니다. scheduled_progresses가 파트별 시작/동작 시간을 독립적으로 계산하고, Together/Sequence/Custom 입력을 미리보기와 실제 PNG/GIF 생성에 공통 적용합니다. 움직이는 회전 중심·동시 동작·부분 겹침을 모의 Rhino 기하 및 실제 FFmpeg 출력으로 검증했습니다.

1.9.1: 설치 EXE에서 RHI 파일 연결 실행을 제거했습니다. Rhino 8/6의 HKLM·HKCU 양쪽 레지스트리 뷰의 Install/Path 및 표준 Program Files 경로에서 rhiexec.exe를 찾고, UseShellExecute=false와 따옴표로 감싼 패키지 경로로 직접 실행합니다. 엔진 탐색은 기존 파일·등록 삭제보다 먼저 수행하며 연결 프로그램 변경/우회 실패 시 연결 프로그램 실행은 하지 않습니다. McNeel 공식 Installer Engine 안내(https://developer.rhino3d.com/guides/general/rhino-installer-engine/)의 RHI 패키지 설치 모델을 참고했습니다. 경로 탐색·실행 설정·기존 설치 검증 회귀를 자동 테스트했고 Windows Rhino Installer 실제 실행은 이 Linux 환경에서 확인하지 못했습니다.

1.9.2: 사용자 환경에서 1.9.1의 제한된 System 경로 탐색으로 엔진 미발견 오류가 재현됨을 확인했습니다. McNeel 공용 폴더 및 Rhino 설치 폴더 하위의 버전·아키텍처 폴더를 깊이 제한 탐색하고 Rhino/McNeel ProgID의 명시적인 rhiexec.exe 명령을 읽습니다. .rhi 연결 프로그램은 사용하지 않으며 7-Zip/셸 명령은 거부합니다. 자동 탐색 실패 시 UI 스레드에서 rhiexec.exe 직접 선택을 제공하며 취소·파일 미발견 모두 기존 설치를 변경하지 않습니다. 공개 포럼과 GitHub 추가 검색은 접근 제한으로 위치를 독립 확인하지 못했으므로 경로 하나를 확정하지 않고 제한된 탐색·직접 선택을 구현했습니다. 실제 파일 트리 기반 공용/버전 경로 탐색, 명령 파싱, 잘못된 엔진 거부와 기존 파일 보존을 테스트했습니다. Windows Rhino 실행 검증은 미수행입니다.
