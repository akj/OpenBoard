"""Native accessibility for the painted board on Windows."""

import chess
import wx


class BoardAccessible(wx.Accessible):
    """Expose the existing focus and selection as accessible chess squares."""

    def __init__(self, panel, square=None, parent=None):
        super().__init__(panel)
        self.panel = panel
        self.square = square
        self.parent = parent
        self.children = (
            [BoardAccessible(panel, square, self) for square in chess.SQUARES]
            if square is None
            else []
        )

    def GetChildCount(self):
        return wx.ACC_OK, len(self.children)

    def GetChild(self, childId):
        if childId == 0:
            return wx.ACC_OK, self
        if 1 <= childId <= len(self.children):
            return wx.ACC_OK, self.children[childId - 1]
        return wx.ACC_FAIL, None

    def GetName(self, childId):
        if childId:
            status, child = self.GetChild(childId)
            return child.GetName(0) if child else (status, "")
        if self.square is None:
            return wx.ACC_OK, self.panel.GetName()
        return wx.ACC_OK, self.panel.controller.square_description(self.square)

    def GetRole(self, childId):
        if childId:
            status, child = self.GetChild(childId)
            return child.GetRole(0) if child else (status, wx.ROLE_SYSTEM_CLIENT)
        return wx.ACC_OK, (
            wx.ROLE_SYSTEM_GROUPING if self.square is None else wx.ROLE_SYSTEM_CELL
        )

    def GetState(self, childId):
        if childId:
            status, child = self.GetChild(childId)
            return child.GetState(0) if child else (status, 0)
        state = wx.ACC_STATE_SYSTEM_FOCUSABLE
        if not self.panel.IsShownOnScreen():
            state |= wx.ACC_STATE_SYSTEM_INVISIBLE | wx.ACC_STATE_SYSTEM_OFFSCREEN
        if self.square is not None:
            state |= wx.ACC_STATE_SYSTEM_SELECTABLE
            if self.panel.selected == self.square:
                state |= wx.ACC_STATE_SYSTEM_SELECTED
            if (
                self.panel.IsShownOnScreen()
                and self.panel.HasFocus()
                and self.panel.focus == self.square
            ):
                state |= wx.ACC_STATE_SYSTEM_FOCUSED
        return wx.ACC_OK, state

    def GetSelections(self):
        if self.square is None and self.panel.selected is not None:
            return wx.ACC_OK, self.panel.selected + 1
        return wx.ACC_OK, None

    def GetFocus(self, childId=0):
        # Native callbacks return both output parameters, the child ID and object.
        if not self.panel.IsShownOnScreen() or not self.panel.HasFocus():
            return wx.ACC_OK, 0, None
        root = self.parent or self
        return wx.ACC_OK, 0, root.children[self.panel.focus]

    def GetParent(self):
        if self.parent:
            return wx.ACC_OK, self.parent
        return wx.ACC_NOT_IMPLEMENTED, None

    def GetValue(self, childId):
        return wx.ACC_OK, ""

    def GetLocation(self, elementId):
        if elementId:
            status, child = self.GetChild(elementId)
            return child.GetLocation(0) if child else (status, wx.Rect())
        if self.square is None:
            return wx.ACC_OK, self.panel.GetScreenRect()
        size = self.panel.square_size
        point = self.panel.ClientToScreen(
            wx.Point(
                chess.square_file(self.square) * size,
                (7 - chess.square_rank(self.square)) * size,
            )
        )
        return wx.ACC_OK, wx.Rect(point, wx.Size(size, size))

    def GetDefaultAction(self, childId):
        return wx.ACC_OK, "Select or move" if self.square is not None or childId else ""

    def DoDefaultAction(self, childId):
        if childId:
            status, child = self.GetChild(childId)
            return child.DoDefaultAction(0) if child else status
        if self.square is None:
            return wx.ACC_FAIL
        wx.CallAfter(self._activate)
        return wx.ACC_OK

    def _activate(self):
        if not self.panel:
            return
        self.panel.SetFocus()
        self.panel.controller.focus_square(self.square)
        self.panel.controller.select()

    def Select(self, childId, selectFlags):
        if childId:
            status, child = self.GetChild(childId)
            return child.Select(0, selectFlags) if child else status
        if self.square is None or selectFlags != wx.ACC_SEL_TAKEFOCUS:
            return wx.ACC_NOT_IMPLEMENTED
        wx.CallAfter(self._focus)
        return wx.ACC_OK

    def _focus(self):
        if self.panel:
            self.panel.SetFocus()
            self.panel.controller.focus_square(self.square)
