/**
 * Bloguito - WhatsApp Remote Control Bridge
 * Powered by @whiskeysockets/baileys (Pure WebSocket Multi-Device Client)
 */

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const pino = require('pino');
const qrcode = require('qrcode');
const qrcodeTerminal = require('qrcode-terminal');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');
const { isAuthorizedChat, parsePublishCommand } = require('./command_policy');

process.umask(0o077);

const AUTH_DIR = path.join(__dirname, 'auth_info_baileys');
const QR_PATH = path.join(__dirname, 'qr.png');
const QR_TMP_PATH = '/tmp/whatsapp_qr.png';
const CLI_PATH = path.join(__dirname, '..', 'editorial_cli.py');
const VENV_PYTHON = path.join(__dirname, '..', 'venv', 'bin', 'python');

function runCommand(command) {
    return new Promise((resolve, reject) => {
        exec(command, { timeout: 60000 }, (error, stdout, stderr) => {
            if (error) {
                resolve({ success: false, output: (stderr || stdout || error.message).trim() });
            } else {
                resolve({ success: true, output: stdout.trim() });
            }
        });
    });
}

async function startBridge() {
    // Auth material is account access, not ordinary cache data.
    fs.mkdirSync(AUTH_DIR, { recursive: true, mode: 0o700 });
    fs.chmodSync(AUTH_DIR, 0o700);
    for (const entry of fs.readdirSync(AUTH_DIR, { withFileTypes: true })) {
        if (entry.isSymbolicLink()) throw new Error('WhatsApp auth directory contains an unexpected symlink');
        if (entry.isFile()) fs.chmodSync(path.join(AUTH_DIR, entry.name), 0o600);
    }
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const sentMessageIds = new Set();

    const sock = makeWASocket({
        logger: pino({ level: 'silent' }),
        auth: state,
        printQRInTerminal: false,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log('\n[WhatsApp Bridge] 📱 새로운 페어링 QR 코드가 생성되었습니다!');
            qrcodeTerminal.generate(qr, { small: true });

            try {
                await qrcode.toFile(QR_PATH, qr, { width: 350, margin: 2 });
                await qrcode.toFile(QR_TMP_PATH, qr, { width: 350, margin: 2 });
                fs.chmodSync(QR_PATH, 0o600);
                fs.chmodSync(QR_TMP_PATH, 0o600);
                console.log(`[WhatsApp Bridge] 🖼️ QR 이미지 저장 완료: ${QR_PATH}`);
            } catch (err) {
                console.error('[WhatsApp Bridge] QR 파일 저장 오류:', err);
            }
        }

        if (connection === 'close') {
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`[WhatsApp Bridge] ⚠️ 연결 종료 (코드: ${statusCode}). 재연결 시도 여부: ${shouldReconnect}`);
            if (shouldReconnect) {
                setTimeout(startBridge, 3000);
            }
        } else if (connection === 'open') {
            console.log('\n==================================================');
            console.log('🚀 [WhatsApp Bridge] 왓츠앱 계정 연결 성공! 24시간 원격 제어 대기 중');
            console.log('==================================================\n');
            if (fs.existsSync(QR_PATH)) fs.unlinkSync(QR_PATH);
            if (fs.existsSync(QR_TMP_PATH)) fs.unlinkSync(QR_TMP_PATH);

            try {
                const myJid = sock.user.id.split(':')[0] + '@s.whatsapp.net';
                const welcome = await sock.sendMessage(myJid, {
                    text: "🚀 *[생활정보 24 원격 비서 연결 완료]*\n\n서버와 왓츠앱이 성공적으로 연결되었습니다!\n지금 바로 */status* 또는 */help* 를 입력해 보세요."
                });
                if (welcome?.key?.id) sentMessageIds.add(welcome.key.id);
            } catch (notifyErr) {
                console.error('[WhatsApp Bridge] 환영 메시지 발송 실패:', notifyErr.message);
            }
        }
    });

    sock.ev.on('messages.upsert', async (m) => {
        try {
            // Reconnected devices may replay old commands as historical messages.
            if (m.type !== 'notify') return;
            const msg = m.messages[0];
            if (!msg || !msg.message) return;
            if (sentMessageIds.has(msg.key.id)) return;

            const sender = msg.key.remoteJid;
            const isFromMe = Boolean(msg.key.fromMe);

            // Group chat ignore
            if (sender.endsWith('@g.us')) return;

            // Extract message text
            const text = (
                msg.message.conversation ||
                msg.message.extendedTextMessage?.text ||
                msg.message.imageMessage?.caption ||
                ''
            ).trim();

            if (!text) return;

            // Only an own-account self-chat or an explicitly permitted owner chat.
            const ownerIds = (process.env.BLOGUITO_WHATSAPP_OWNER_IDS || '').split(',').map(id => id.trim()).filter(Boolean);
            if (!isAuthorizedChat({
                remoteJid: sender,
                fromMe: isFromMe,
                ownJids: [sock.user?.id, sock.user?.lid],
                ownerIds,
            })) {
                console.log(`[WhatsApp Bridge] 🛑 인가되지 않은 발신자 차단 (${sender})`);
                return;
            }

            console.log(`[WhatsApp Bridge] 📩 수신 메시지 (${sender}, fromMe=${isFromMe}): "${text}"`);

            // Helper reply function
            const reply = async (replyText) => {
                const sent = await sock.sendMessage(sender, { text: replyText }, { quoted: msg });
                if (sent?.key?.id) {
                    sentMessageIds.add(sent.key.id);
                    // Keep Set bounded
                    if (sentMessageIds.size > 200) {
                        const first = sentMessageIds.values().next().value;
                        sentMessageIds.delete(first);
                    }
                }
            };

            const lower = text.toLowerCase();

            // 1. Help
            if (lower === '/help' || lower === '도움말' || lower === 'help' || lower === '?') {
                const helpMsg =
                    "🤖 *[생활정보 24 원격 비서]*\n\n" +
                    "스마트폰에서 블로그를 직접 제어할 수 있는 명령어입니다:\n\n" +
                    "📋 */list* 또는 *초안* : 대기 중인 임시글 목록\n" +
                    "🚀 */publish <ID>* : 검증이 최신 상태인 해당 번호 초안만 정식 공개 (예: /publish 81)\n" +
                    "📊 */status* 또는 *상태* : 서버 자원 및 사이트 상태\n" +
                    "🤖 */quota* 또는 *사용량* : Gemini 모델별 로컬 추정 사용량\n" +
                    "💾 */backup* 또는 *백업* : 데이터베이스·미디어·설정 통합 백업\n" +
                    "❓ */help* : 명령어 안내";
                await reply(helpMsg);
                return;
            }

            // 2. Draft List
            if (lower === '/list' || text === '초안' || text === '목록' || lower === '/drafts') {
                await reply("⏳ 대기 중인 초안 목록을 조회하고 있습니다...");
                const pythonBin = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : 'python3';
                const res = await runCommand(`${pythonBin} ${CLI_PATH} list-drafts`);

                if (res.success && res.output) {
                    await reply(`📋 *[현재 대기 중인 초안]*\n\n\`\`\`\n${res.output}\n\`\`\`\n👉 정식 공개하려면 */publish <ID>* 를 보내주세요.`);
                } else {
                    await reply(`ℹ️ 대기 중인 초안이 없거나 조회에 실패했습니다:\n${res.output}`);
                }
                return;
            }

            // 3. Promote Draft
            const postId = parsePublishCommand(text);
            if (postId !== null) {
                await reply(`⏳ 포스트 #${postId} 정식 공개 전 원고·출처 검증을 시작합니다...`);

                const pythonBin = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : 'python3';
                const res = await runCommand(`${pythonBin} ${CLI_PATH} promote-draft ${postId} --confirm-publish`);

                if (res.success) {
                    await reply(`🎉 *포스트 #${postId} 정식 공개 완료!*\n\n• 링크: https://lifeinfo24.org/?p=${postId}\n• 편집 근거 재확인과 WordPress 게시 상태·내부 색인 확인이 완료되었습니다.`);
                } else {
                    await reply(`❌ 발행 처리 중 오류 발생:\n${res.output}`);
                }
                return;
            }
            if (/^\/publish(?:\s|$)/i.test(text)) {
                await reply("⚠️ 공개 명령 형식은 /publish 81 입니다. 글 ID 하나만 입력해 주세요.");
                return;
            }

            // 4. Status
            if (lower === '/status' || text === '상태' || lower === 'status') {
                const memRes = await runCommand("free -m | awk 'NR==2{printf \"메모리: %sMB / %sMB (사용률: %.1f%%)\", $3,$2,$3*100/$2 }'");
                const diskRes = await runCommand("df -h / | awk 'NR==2{printf \"디스크: %s / %s (사용률: %s)\", $3,$2,$5 }'");
                const uptimeRes = await runCommand("uptime -p");

                const statusMsg =
                    "📊 *[생활정보 24 서버 인프라 상태]*\n\n" +
                    `• ${memRes.output}\n` +
                    `• ${diskRes.output}\n` +
                    `• 가동 시간: ${uptimeRes.output}\n` +
                    "• 도메인: https://lifeinfo24.org\n" +
                    "• 관리자: https://lifeinfo24.org/wp-admin";
                await reply(statusMsg);
                return;
            }

            // 5. Backup
            if (lower === '/backup' || text === '백업') {
                await reply("⏳ 통합 백업 스크립트를 실행합니다...");
                const backupScript = path.join(__dirname, '..', 'backup_daily.sh');
                const res = await runCommand(`bash ${backupScript}`);
                if (res.success) {
                    await reply("💾 *백업 명령 완료.* 백업 파일의 오프사이트 보관과 실제 복원 성공 여부는 별도로 확인해야 합니다.");
                } else {
                    await reply(`⚠️ 백업 실패:\n${res.output}`);
                }
                return;
            }

            // 6. Quota Check
            if (lower === '/quota' || text === '사용량' || text === '할당량' || lower === '/limit') {
                const pythonBin = fs.existsSync(VENV_PYTHON) ? VENV_PYTHON : 'python3';
                const parentDir = path.join(__dirname, '..');
                const res = await runCommand(`PYTHONPATH=${parentDir} ${pythonBin} -c "from agents.quota_tracker import format_quota_summary; print(format_quota_summary())"`);
                if (res.success && res.output) {
                    await reply(`📊 *[Gemini API 금일 할당량 현황]*\n\n${res.output}\n\n💡 _최신 모델(3.6 Flash) 한도 소진 시 백업 모델(3.5 Flash Lite 500회)로 자동 전환됩니다._`);
                } else {
                    await reply(`⚠️ 할당량 조회 실패:\n${res.output}`);
                }
                return;
            }

        } catch (err) {
            console.error('[WhatsApp Bridge] 메시지 처리 에러:', err);
        }
    });
}

startBridge().catch((err) => {
    console.error('[WhatsApp Bridge] 치명적 시작 오류:', err);
});
