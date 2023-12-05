# -*- coding: utf-8 -*-

import pytest
from unittest.mock import MagicMock


dummy_dev = MagicMock(
    **{
        "is_kernel_driver_active.return_value": True,
    }
)


@pytest.fixture(scope="class")
def setup(request, class_mocker):
    import usb.backend  # type: ignore
    import usb  # type: ignore

    class_mocker.patch.object(usb.backend, "libusb1")
    class_mocker.patch.object(usb.core, "find", return_value=[dummy_dev])

    yield


@pytest.mark.usefixtures("setup")
class TestUsbLamp(object):
    def test_color(self):
        import pyusblamp

        lamp = pyusblamp.USBLamp()
        assert dummy_dev.ctrl_transfer.call_count == 4
        assert dummy_dev.ctrl_transfer.call_args_list[3].args[4][:3] == (0x00, 0x00, 0x00)

        color = lamp.get_color()
        assert color == (0x00, 0x00, 0x00)

        lamp.set_color((0x50, 0x50, 0x50))
        color = lamp.get_color()
        assert color == (0x40, 0x40, 0x40)
        assert dummy_dev.ctrl_transfer.call_count == 5
        assert dummy_dev.ctrl_transfer.call_args_list[4].args[4][:3] == (0x40, 0x40, 0x40)

        lamp.set_color((-0x50, -0x50, -0x50))
        color = lamp.get_color()
        assert color == (0x00, 0x00, 0x00)
        assert dummy_dev.ctrl_transfer.call_count == 6
        assert dummy_dev.ctrl_transfer.call_args_list[5].args[4][:3] == (0x00, 0x00, 0x00)
