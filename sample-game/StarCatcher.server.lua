--[[
	⭐ 별 받기 (StarCatcher) — 클라우드 세션 연동 테스트용 샘플 게임

	【설치 방법 — 딱 1번 붙여넣기】
	1. Roblox Studio에서 새 Baseplate 플레이스 열기
	2. 왼쪽 탐색기(Explorer)에서 ServerScriptService 찾기
	3. ServerScriptService 우클릭 → Insert Object → Script
	4. 새로 생긴 Script를 더블클릭해서 열고, 안의 내용 전부 지우기
	5. 이 파일 내용 전체를 복사해서 붙여넣기
	6. 위쪽 [▶ Play] 버튼 누르기

	【게임 내용】
	하늘에서 반짝이는 별 구슬이 떨어진다 → 캐릭터로 몸을 부딪히면 "팡!" 터지면서
	⭐별 +1 (화면 오른쪽 위 리더보드에 표시). 그게 전부! 연동 확인용 미니 게임.
]]

local Players = game:GetService("Players")
local Debris = game:GetService("Debris")

-- ──────────────────────────────── 설정값 ────────────────────────────────
local SPAWN_INTERVAL = 1.2   -- 몇 초마다 별이 떨어질지
local SPAWN_RADIUS = 40      -- 스폰 지점(0,0,0) 주변 몇 스터드 안에 떨어질지
local SPAWN_HEIGHT = 60      -- 떨어지기 시작하는 높이
local ORB_LIFETIME = 25      -- 안 주우면 몇 초 뒤 사라질지

local ORB_COLORS = {
	Color3.fromRGB(255, 221, 85),  -- 금색
	Color3.fromRGB(85, 170, 255),  -- 하늘색
	Color3.fromRGB(255, 120, 180), -- 분홍
	Color3.fromRGB(130, 255, 130), -- 연두
	Color3.fromRGB(190, 130, 255), -- 보라
}

-- ──────────────────────────── 리더보드 (⭐별) ────────────────────────────
Players.PlayerAdded:Connect(function(player)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	stats.Parent = player

	local stars = Instance.new("IntValue")
	stars.Name = "⭐별"
	stars.Value = 0
	stars.Parent = stats
end)

-- ──────────────────────────── 터지는 연출 ────────────────────────────
local function popEffect(position, color)
	local holder = Instance.new("Part")
	holder.Anchored = true
	holder.CanCollide = false
	holder.Transparency = 1
	holder.Size = Vector3.new(1, 1, 1)
	holder.CFrame = CFrame.new(position)
	holder.Parent = workspace

	local particles = Instance.new("ParticleEmitter")
	particles.Color = ColorSequence.new(color)
	particles.LightEmission = 1
	particles.Lifetime = NumberRange.new(0.3, 0.6)
	particles.Speed = NumberRange.new(10, 18)
	particles.SpreadAngle = Vector2.new(180, 180)
	particles.Size = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.6),
		NumberSequenceKeypoint.new(1, 0),
	})
	particles.Enabled = false
	particles.Parent = holder
	particles:Emit(25)

	local sound = Instance.new("Sound")
	sound.SoundId = "rbxasset://sounds/electronicpingshort.wav"
	sound.PlaybackSpeed = 1 + math.random() * 0.4
	sound.Volume = 0.8
	sound.Parent = holder
	sound:Play()

	Debris:AddItem(holder, 2)
end

-- ──────────────────────────── 별 구슬 스폰 ────────────────────────────
local function spawnOrb()
	local color = ORB_COLORS[math.random(#ORB_COLORS)]

	local orb = Instance.new("Part")
	orb.Name = "StarOrb"
	orb.Shape = Enum.PartType.Ball
	orb.Size = Vector3.new(3, 3, 3)
	orb.Material = Enum.Material.Neon
	orb.Color = color
	orb.TopSurface = Enum.SurfaceType.Smooth
	orb.BottomSurface = Enum.SurfaceType.Smooth
	orb.Position = Vector3.new(
		math.random(-SPAWN_RADIUS, SPAWN_RADIUS),
		SPAWN_HEIGHT,
		math.random(-SPAWN_RADIUS, SPAWN_RADIUS)
	)
	orb.Parent = workspace

	local sparkles = Instance.new("Sparkles")
	sparkles.SparkleColor = color
	sparkles.Parent = orb

	local popped = false
	orb.Touched:Connect(function(hit)
		if popped then
			return
		end
		local character = hit.Parent
		local player = character and Players:GetPlayerFromCharacter(character)
		if not player then
			return
		end
		popped = true

		local stats = player:FindFirstChild("leaderstats")
		local stars = stats and stats:FindFirstChild("⭐별")
		if stars then
			stars.Value += 1
		end

		popEffect(orb.Position, color)
		orb:Destroy()
	end)

	Debris:AddItem(orb, ORB_LIFETIME)
end

-- ──────────────────────────── 메인 루프 ────────────────────────────
print("⭐ 별 받기 샘플 시작! 하늘에서 별이 떨어집니다 — 몸으로 받아 보세요.")

while true do
	spawnOrb()
	task.wait(SPAWN_INTERVAL)
end
