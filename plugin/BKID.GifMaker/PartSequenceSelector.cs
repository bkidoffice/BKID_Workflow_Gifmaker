using System;
using System.Collections.Generic;
using Rhino;
using Rhino.Input;
using Rhino.Input.Custom;

namespace BKID.GifMaker
{
    public sealed class PartSequenceSelection
    {
        public bool Finished { get; internal set; }
        public bool Cancelled { get; internal set; }
        public Guid[] ObjectIds { get; internal set; }
    }
    public static class PartSequenceSelector
    {
        public static PartSequenceSelection Pick(bool allowFinish, Guid[] excludedIds)
        {
            var excluded = new HashSet<Guid>(excludedIds ?? new Guid[0]);
            using (var get = new GetObject())
            {
                get.SetCommandPrompt(allowFinish
                    ? "다음 부품을 선택하세요 (Enter: 전체 이동 설정 완료 / Esc: 전체 취소)"
                    : "Datum CSYS로 이동할 첫 부품을 선택하세요");
                get.EnablePreSelect(!allowFinish, true);
                get.SubObjectSelect = false;
                get.GroupSelect = false;
                get.SetCustomGeometryFilter((obj, geometry, component) => obj != null && !excluded.Contains(obj.Id));
                get.AcceptNothing(allowFinish);
                var result = get.GetMultiple(1, 0);
                if (result == GetResult.Nothing && allowFinish)
                    return new PartSequenceSelection { Finished = true, ObjectIds = new Guid[0] };
                if (result != GetResult.Object)
                    return new PartSequenceSelection { Cancelled = true, ObjectIds = new Guid[0] };
                var ids = new Guid[get.ObjectCount];
                for (int i = 0; i < ids.Length; i++) ids[i] = get.Object(i).ObjectId;
                return new PartSequenceSelection { ObjectIds = ids };
            }
        }
    }
}
