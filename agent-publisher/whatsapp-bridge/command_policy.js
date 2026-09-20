'use strict';

// Keep command authorization independent of the WhatsApp client so that it can
// be tested without connecting an account or executing a publish command.
function normalizedChatJid(jid) {
    const match = /^(\d+)(?::\d+)?@(s\.whatsapp\.net|lid)$/.exec(jid || '');
    return match ? `${match[1]}@${match[2]}` : null;
}

function isAuthorizedChat({ remoteJid, fromMe, ownJids = [], ownerIds = [] }) {
    const chat = normalizedChatJid(remoteJid);
    if (!chat) return false;

    // A message sent by this account to *another* person is not an instruction.
    if (fromMe) {
        return ownJids.some(jid => normalizedChatJid(jid) === chat);
    }

    // Explicitly configured owners may command the bot in their own 1:1 chat.
    const chatId = chat.split('@')[0];
    return ownerIds.some(id => /^\d+$/.test(id) && id === chatId);
}

function parsePublishCommand(text) {
    const match = /^\/publish\s+([1-9]\d*)$/i.exec((text || '').trim());
    if (!match || !Number.isSafeInteger(Number(match[1]))) return null;
    return match[1];
}

module.exports = { isAuthorizedChat, parsePublishCommand };
