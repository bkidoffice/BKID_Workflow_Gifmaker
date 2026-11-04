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

GIF89a 인코더는 이 프로젝트에서 구현했습니다. 256색 고정 팔레트, 9-bit LZW 사전의 조기 초기화, NETSCAPE 반복 확장을 사용합니다. Pillow는 개발 테스트에서 결과 GIF를 독립적으로 디코딩하는 용도로만 사용하며 플러그인에 배포하지 않습니다.
