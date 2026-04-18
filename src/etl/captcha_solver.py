"""Optional captcha solver integration for live scrapers.

The solver is deliberately disabled by default. Configure it with:

- SCRAPER_CAPTCHA_PROVIDER=2captcha
- SCRAPER_CAPTCHA_API_KEY=<provider key>
"""

from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass

from playwright.async_api import Page


@dataclass(frozen=True)
class CaptchaChallenge:
    captcha_type: str
    sitekey: str


@dataclass(frozen=True)
class CaptchaResult:
    detected: bool
    solved: bool
    error: str = ""
    captcha_type: str = ""


def _post_form(url: str, data: dict[str, str], timeout: int = 30) -> dict:
    encoded = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(url, data=encoded, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, data: dict, timeout: int = 30) -> dict:
    encoded = json.dumps(data).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_json(url: str, params: dict[str, str], timeout: int = 30) -> dict:
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{query}", timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


async def extract_captcha_challenge(page: Page) -> CaptchaChallenge | None:
    """Find common reCAPTCHA or hCaptcha sitekeys in the rendered page."""
    challenge = await page.evaluate(
        """
        () => {
          const direct = document.querySelector('[data-sitekey]');
          if (direct?.getAttribute('data-sitekey')) {
            const sitekey = direct.getAttribute('data-sitekey');
            const html = direct.outerHTML.toLowerCase();
            return {
              captcha_type: html.includes('hcaptcha') ? 'hcaptcha' : 'recaptcha',
              sitekey
            };
          }

          for (const frame of Array.from(document.querySelectorAll('iframe[src]'))) {
            const src = frame.getAttribute('src') || '';
            const isCaptcha = src.includes('recaptcha') || src.includes('hcaptcha');
            if (!isCaptcha) continue;
            try {
              const url = new URL(src, window.location.href);
              const sitekey = url.searchParams.get('k') || url.searchParams.get('sitekey');
              if (sitekey) {
                return {
                  captcha_type: src.includes('hcaptcha') ? 'hcaptcha' : 'recaptcha',
                  sitekey
                };
              }
            } catch (_) {}
          }
          return null;
        }
        """
    )
    if not challenge:
        return None
    return CaptchaChallenge(
        captcha_type=challenge["captcha_type"],
        sitekey=challenge["sitekey"],
    )


async def inject_captcha_token(page: Page, token: str, captcha_type: str) -> None:
    """Inject a provider token into common hidden captcha response fields."""
    await page.evaluate(
        """
        ({ token, captchaType }) => {
          const selectors = captchaType === 'hcaptcha'
            ? ['textarea[name="h-captcha-response"]', '#h-captcha-response']
            : ['textarea[name="g-recaptcha-response"]', '#g-recaptcha-response'];

          for (const selector of selectors) {
            let element = document.querySelector(selector);
            if (!element) {
              element = document.createElement('textarea');
              element.name = selector.includes('h-captcha') ? 'h-captcha-response' : 'g-recaptcha-response';
              element.id = element.name;
              element.style.display = 'none';
              document.body.appendChild(element);
            }
            element.value = token;
            element.dispatchEvent(new Event('input', { bubbles: true }));
            element.dispatchEvent(new Event('change', { bubbles: true }));
          }

          window.__scraperCaptchaToken = token;
        }
        """,
        {"token": token, "captchaType": captcha_type},
    )


async def solve_with_2captcha(
    challenge: CaptchaChallenge,
    page_url: str,
    api_key: str,
    *,
    poll_seconds: float = 5.0,
    max_attempts: int = 24,
) -> str:
    method = "hcaptcha" if challenge.captcha_type == "hcaptcha" else "userrecaptcha"
    payload = {
        "key": api_key,
        "method": method,
        "pageurl": page_url,
        "json": "1",
    }
    if challenge.captcha_type == "hcaptcha":
        payload["sitekey"] = challenge.sitekey
    else:
        payload["googlekey"] = challenge.sitekey

    create_response = await asyncio.to_thread(
        _post_form,
        "https://2captcha.com/in.php",
        payload,
    )
    if create_response.get("status") != 1:
        raise RuntimeError(create_response.get("request", "2captcha_create_failed"))

    request_id = create_response["request"]
    for _ in range(max_attempts):
        await asyncio.sleep(poll_seconds)
        poll_response = await asyncio.to_thread(
            _get_json,
            "https://2captcha.com/res.php",
            {
                "key": api_key,
                "action": "get",
                "id": request_id,
                "json": "1",
            },
        )
        if poll_response.get("status") == 1:
            return poll_response["request"]
        if poll_response.get("request") != "CAPCHA_NOT_READY":
            raise RuntimeError(poll_response.get("request", "2captcha_poll_failed"))

    raise TimeoutError("captcha_solver_timeout")


async def solve_with_capsolver(
    challenge: CaptchaChallenge,
    page_url: str,
    api_key: str,
    *,
    poll_seconds: float = 5.0,
    max_attempts: int = 24,
) -> str:
    task_type = (
        "HCaptchaTaskProxyLess"
        if challenge.captcha_type == "hcaptcha"
        else "ReCaptchaV2TaskProxyLess"
    )
    create_response = await asyncio.to_thread(
        _post_json,
        "https://api.capsolver.com/createTask",
        {
            "clientKey": api_key,
            "task": {
                "type": task_type,
                "websiteURL": page_url,
                "websiteKey": challenge.sitekey,
            },
        },
    )
    if create_response.get("errorId"):
        raise RuntimeError(create_response.get("errorDescription", "capsolver_create_failed"))

    task_id = create_response["taskId"]
    for _ in range(max_attempts):
        await asyncio.sleep(poll_seconds)
        poll_response = await asyncio.to_thread(
            _post_json,
            "https://api.capsolver.com/getTaskResult",
            {"clientKey": api_key, "taskId": task_id},
        )
        if poll_response.get("status") == "ready":
            return poll_response["solution"]["gRecaptchaResponse"]
        if poll_response.get("errorId"):
            raise RuntimeError(poll_response.get("errorDescription", "capsolver_poll_failed"))

    raise TimeoutError("captcha_solver_timeout")


async def solve_with_anticaptcha(
    challenge: CaptchaChallenge,
    page_url: str,
    api_key: str,
    *,
    poll_seconds: float = 5.0,
    max_attempts: int = 24,
) -> str:
    task_type = (
        "HCaptchaTaskProxyless"
        if challenge.captcha_type == "hcaptcha"
        else "NoCaptchaTaskProxyless"
    )
    create_response = await asyncio.to_thread(
        _post_json,
        "https://api.anti-captcha.com/createTask",
        {
            "clientKey": api_key,
            "task": {
                "type": task_type,
                "websiteURL": page_url,
                "websiteKey": challenge.sitekey,
            },
        },
    )
    if create_response.get("errorId"):
        raise RuntimeError(
            create_response.get("errorDescription", "anticaptcha_create_failed")
        )

    task_id = create_response["taskId"]
    for _ in range(max_attempts):
        await asyncio.sleep(poll_seconds)
        poll_response = await asyncio.to_thread(
            _post_json,
            "https://api.anti-captcha.com/getTaskResult",
            {"clientKey": api_key, "taskId": task_id},
        )
        if poll_response.get("status") == "ready":
            return poll_response["solution"]["gRecaptchaResponse"]
        if poll_response.get("errorId"):
            raise RuntimeError(
                poll_response.get("errorDescription", "anticaptcha_poll_failed")
            )

    raise TimeoutError("captcha_solver_timeout")


async def solve_captcha_if_configured(page: Page, page_url: str) -> CaptchaResult:
    """Detect and solve a visible captcha only when provider credentials exist."""
    challenge = await extract_captcha_challenge(page)
    if challenge is None:
        return CaptchaResult(detected=False, solved=False)

    provider = os.getenv("SCRAPER_CAPTCHA_PROVIDER", "").strip().lower()
    api_key = os.getenv("SCRAPER_CAPTCHA_API_KEY", "").strip()
    if not provider or not api_key:
        return CaptchaResult(
            detected=True,
            solved=False,
            error="captcha_solver_not_configured",
            captcha_type=challenge.captcha_type,
        )

    solvers = {
        "2captcha": solve_with_2captcha,
        "capsolver": solve_with_capsolver,
        "anti-captcha": solve_with_anticaptcha,
        "anticaptcha": solve_with_anticaptcha,
    }
    solver = solvers.get(provider)
    if solver is None:
        return CaptchaResult(
            detected=True,
            solved=False,
            error=f"unsupported_captcha_provider:{provider}",
            captcha_type=challenge.captcha_type,
        )

    try:
        token = await solver(challenge, page_url, api_key)
        await inject_captcha_token(page, token, challenge.captcha_type)
        return CaptchaResult(
            detected=True,
            solved=True,
            captcha_type=challenge.captcha_type,
        )
    except Exception as exc:
        return CaptchaResult(
            detected=True,
            solved=False,
            error=f"captcha_solver_failed:{exc}",
            captcha_type=challenge.captcha_type,
        )
