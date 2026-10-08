-- 소리 창고 (클라 전용 — 서버는 소리를 내지 않아요)
-- rbxasset:// 엔진 내장 소리만 사용. 앞 후보가 실패하면 다음 후보로 폴백.
-- SoundBank.play("이름", {pitch=, volume=, pos=}) 로 어디서든 재생.

local SoundService = game:GetService("SoundService")
local Debris = game:GetService("Debris")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local SoundBank = {}

-- 공용 폴백 후보들
local THUD = "rbxasset://sounds/action_jump_land.mp3"
local WHOOSH = "rbxasset://sounds/action_falling.mp3"
local SNAP = "rbxasset://sounds/snap.mp3"

-- 이름 → 후보 SoundId 배열 (앞이 실패하면 다음 후보)
local SOUND_TABLE = {
	ping = {"rbxasset://sounds/electronicpingshort.wav"},
	snap = {SNAP},
	splash = {"rbxasset://sounds/impact_water.mp3"},
	thud = {THUD},
	whoosh = {WHOOSH},
	step = {"rbxasset://sounds/action_footsteps_plastic.mp3"},
	getup = {"rbxasset://sounds/action_get_up.mp3"},
	ouch = {"rbxasset://sounds/uuhhh.mp3"},
	collide = {"rbxasset://sounds/collide.wav", THUD},
	slash = {"rbxasset://sounds/swordslash.wav", WHOOSH},
	lunge = {"rbxasset://sounds/swordlunge.wav", WHOOSH},
	unsheath = {"rbxasset://sounds/unsheath.wav", SNAP},
}

-- 이름별로 "확정된" SoundId 캐시 (한 번 정하면 계속 그걸 씀)
local chosen = {}

-- 같은 프레임 동시 재생 캡 (최대 4개)
local playedThisFrame = 0
local frameConn = nil
local function ensureFrameReset()
	if not frameConn then
		frameConn = RunService.Heartbeat:Connect(function()
			playedThisFrame = 0
		end)
	end
end

-- 사운드 인스턴스 만들기
-- (없는 rbxasset 경로를 넣어도 Lua 에러는 안 나요 — 그냥 "무음"이 될 뿐.
--  그래서 실패 감지는 pcall이 아니라 아래 play()의 IsLoaded 확인으로 해요)
local function makeSound(soundId)
	local s = Instance.new("Sound")
	s.SoundId = soundId
	return s
end

-- 이름으로 SoundId 고르기
local function pickId(name)
	if chosen[name] then
		return chosen[name]
	end
	local candidates = SOUND_TABLE[name]
	if not candidates then
		return nil
	end
	chosen[name] = candidates[1]
	return chosen[name]
end

-- 실패한 후보(failedId)의 다음 후보로 넘어가기 (다음 호출부터 적용)
local function fallback(name, failedId)
	local candidates = SOUND_TABLE[name]
	if not candidates then
		return
	end
	if chosen[name] ~= failedId then
		return  -- 이미 다른 후보로 넘어간 뒤면 그대로 둬요 (중복 폴백 방지)
	end
	for i, id in ipairs(candidates) do
		if id == failedId and candidates[i + 1] then
			chosen[name] = candidates[i + 1]
			return
		end
	end
end

-- 메인 재생 함수
-- opts: pitch(기본 1), volume(기본 0.5), pos(Vector3이면 3D 재생)
function SoundBank.play(name, opts)
	ensureFrameReset()
	if playedThisFrame >= 4 then
		return  -- 동시 재생 4개 캡
	end
	opts = opts or {}

	local soundId = pickId(name)
	if not soundId then
		return
	end

	local sound = makeSound(soundId)

	local pitch = opts.pitch or 1
	-- 랜덤 피치: 최종 = 피치 × (0.94 ~ 1.06)
	sound.PlaybackSpeed = pitch * (0.94 + math.random() * 0.12)
	sound.Volume = opts.volume or 0.5

	if opts.pos then
		-- 3D 재생: 임시 투명 앵커 파트에 붙이기
		local part = Instance.new("Part")
		part.Name = "소리파트"
		part.Size = Vector3.new(0.2, 0.2, 0.2)
		part.Transparency = 1
		part.Anchored = true
		part.CanCollide = false
		part.CanTouch = false
		part.CanQuery = false
		part.CFrame = CFrame.new(opts.pos)
		sound.RollOffMaxDistance = 300
		sound.Parent = part
		part.Parent = Workspace
		sound:Play()
		Debris:AddItem(part, 3)
	else
		-- 2D 재생
		sound.Parent = SoundService
		sound:Play()
		Debris:AddItem(sound, 3)
	end

	playedThisFrame += 1

	-- 로드 실패 감지: 1초 뒤에도 IsLoaded가 아니면 그 경로는 "없는 소리"로 보고
	-- 다음 후보로 폴백 (이번 재생은 무음이지만, 다음 호출부터 폴백 후보가 나와요)
	if not sound.IsLoaded then
		task.delay(1, function()
			if not sound.IsLoaded then
				fallback(name, soundId)
			end
		end)
	end
end

return SoundBank
