local key = KEYS[1]
local priceStr = ARGV[1] -- 가격은 문자열 그대로 유지 (DB 저장용)
local priceNum = tonumber(ARGV[1]) -- 비교용 숫자
local vol = tonumber(ARGV[2])

-- 최초 틱이면 시/고/저/종가를 모두 현재가로 세팅
if redis.call('EXISTS', key) == 0 then
	redis.call('HSET', key, 'open', priceStr, 'high', priceStr, 'low', priceStr, 'close', priceStr, 'volume', vol)
	redis.call('EXPIRE', key, 300)
else
-- 기존 캔들이 있으면 갱신
	redis.call('HSET', key, 'close', priceStr)
	redis.call('HINCRBY', key, 'volume', vol)

	local highNum = tonumber(redis.call('HGET', key, 'high'))
	if priceNum > highNum then
		redis.call('HSET', key, 'high', priceStr)
	end

	local lowNum = tonumber(redis.call('HGET', key, 'low'))
	if priceNum < lowNum then
		redis.call('HSET', key, 'low', priceStr)
	end
end

return 1