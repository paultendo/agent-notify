class AgentNotify < Formula
  desc "Cross-platform notifications for AI coding agents (Codex, Claude Code, Gemini CLI)"
  homepage "https://github.com/paultendo/agent-notify"
  url "https://github.com/paultendo/agent-notify/archive/refs/tags/v1.1.0.tar.gz"
  sha256 "920c910f8c0714ba0a3d30000c9250fceb2bfb962bafae800cf6868712b2a15b"
  license "MIT"

  def install
    bin.install "agent-notify"
  end

  test do
    assert_match "agent-notify", shell_output("#{bin}/agent-notify --version")
  end
end
