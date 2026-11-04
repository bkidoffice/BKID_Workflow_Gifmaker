using System;
using System.Threading.Tasks;

namespace BKID.GifMaker.Setup
{
    internal static class InstallWorkflow
    {
        // Await resumes on the wizard's UI context before showing the confirmation.
        internal static async Task<bool> RunAsync(Func<bool> detect, Func<bool> confirm, Action<bool> install)
        {
            bool existing = await Task.Run(detect);
            if (existing && !confirm()) return false;
            await Task.Run(() => install(existing));
            return true;
        }

        internal static void RequireConsent(bool existing, bool replacementAllowed)
        {
            if (existing && !replacementAllowed)
                throw new InvalidOperationException("새로 발견된 기존 설치가 있습니다. 설치 버튼을 다시 눌러 삭제·재설치를 확인해 주세요. 기존 설치는 변경하지 않았습니다.");
        }
    }
}
