"""Shared fake eSCL client for coordinator/service/button tests."""
import asyncio

from custom_components.escl_scan.scanner import JobInfo


class FakeClient:
    def __init__(
        self, docs=None, *, job_state="Completed", pages=None,
        source="Platen", gate=None, hang=False, caps=None,
    ):
        self._docs = [list(d) for d in (docs or [])]
        self.caps = caps
        self.create_kwargs = None
        self.job_state = job_state
        self.pages = pages
        self._source = source
        self._gate = gate
        self._hang = hang
        self.deleted = []
        self.closed = False
        self.host = "192.0.2.10"
        self.origin = "http://192.0.2.10"

    async def detect_source(self):
        return self._source

    async def get_capabilities(self):
        if self.caps is None:
            raise OSError("no capabilities endpoint")
        return self.caps

    async def create_job(self, **kwargs):
        self.create_kwargs = kwargs
        return "https://scanner/eSCL/ScanJobs/j1"

    async def iter_next_document(self, url):
        if self._hang:
            await asyncio.Event().wait()  # blocks until cancelled
        if self._gate is not None:
            await self._gate.wait()
        if self._docs:
            for chunk in self._docs.pop(0):
                yield chunk

    async def get_job_info(self, url):
        return JobInfo(
            state=self.job_state, state_reasons=None, pages_completed=self.pages
        )

    async def delete_job(self, url):
        self.deleted.append(url)
        return True

    async def async_close(self):
        self.closed = True
