-- 메인 (클라 진입점 — 유일한 LocalScript)
-- 리모트를 기다렸다가 카메라 → HUD → 연출 → 입력 순서로 켜고,
-- 서버에서 오는 HitFx/Stage 이벤트를 각 모듈에 나눠줘요.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local CameraMod = require(script.Parent.Camera)
local Input = require(script.Parent.Input)
local Hud = require(script.Parent.Hud)
local Fx = require(script.Parent.Fx)

local GameFolder = ReplicatedStorage:WaitForChild("Game")
local Config = require(GameFolder:WaitForChild("Config"))

local player = Players.LocalPlayer

-- 리모트 기다리기
local RemotesFolder = GameFolder:WaitForChild("Remotes")
local Remotes = {
	Hit = RemotesFolder:WaitForChild("Hit"),
	HitFx = RemotesFolder:WaitForChild("HitFx"),
	Stage = RemotesFolder:WaitForChild("Stage"),
	Ready = RemotesFolder:WaitForChild("Ready"),
	Buy = RemotesFolder:WaitForChild("Buy"),
}

-- 지금 스테이지 (HP바 글자용)
local currentStage = 1
-- 이번 건물을 내가 때렸는지 (붕괴 보너스 문구용 — 로컬에서만 기억)
local iHitThisBuilding = false

-- 모듈 켜기 (셰이크 함수 등 공유는 Init 인자로 주입)
CameraMod.Init()
Hud.Init(Remotes, Fx)
Fx.Init(CameraMod.Shake)
Input.Init(Remotes, function()
	Fx.StartSwing()   -- 스윙 선반영
	Hud.AddCombo()    -- 콤보는 표시 전용
end)

-- 서버 → 타격 연출
Remotes.HitFx.OnClientEvent:Connect(function(attackerUserId, damage, isCrit, hitPos, newHp, maxHp)
	if attackerUserId == player.UserId then
		iHitThisBuilding = true
	end
	Fx.OnHitFx(attackerUserId, damage, isCrit, hitPos, newHp, maxHp)
	Hud.UpdateHP(currentStage, newHp, maxHp)
end)

-- 서버 → 스테이지 이벤트
Remotes.Stage.OnClientEvent:Connect(function(ev, stage, hp, maxHp, bonus)
	currentStage = stage

	if ev == "sync" then
		-- 늦은 입장 1회 동기화
		CameraMod.SetStage(stage)
		Hud.UpdateHP(stage, hp, maxHp)

	elseif ev == "collapse" then
		-- 와르르!!
		Fx.CollapseFx()
		Hud.UpdateHP(stage, 0, maxHp)
		local text = "와르르!!"
		if iHitThisBuilding and bonus > 0 then
			text = text .. "  +" .. Config.comma(bonus) .. "원!"
		end
		Hud.Banner(text, -6, 1.2)
		iHitThisBuilding = false

	elseif ev == "new" then
		-- 새 건물 등장 (카메라는 추적 lerp가 알아서 새 높이로 이동)
		CameraMod.SetStage(stage)
		Fx.RevealBuilding(stage)
		Hud.FillHP(stage, maxHp)
		Hud.Banner("스테이지 " .. stage .. "!", 0, 1.4)
	end
end)

-- 핸들러 연결 끝 → 서버에 "준비됐어요" 신호 (서버가 현재 건물 상태를 sync로 보내줘요.
--  접속 직후 서버가 먼저 보낸 sync는 핸들러 연결 전이라 유실될 수 있어서 꼭 필요!)
Remotes.Ready:FireServer()

print("[건물부수기] 준비 완료! 화면 아무 데나 연타하세요!")
