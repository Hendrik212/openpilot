from cereal import car
from selfdrive.car import apply_std_steer_torque_limits
from selfdrive.car.volkswagen import volkswagencan
from selfdrive.car.volkswagen.values import DBC, CANBUS, MQB_LDW_MESSAGES, BUTTON_STATES, CarControllerParams
from opendbc.can.packer import CANPacker
from common.params import Params
from common.realtime import sec_since_boot

class CarController():
  def __init__(self, dbc_name, CP, VM):
    self.apply_steer_last = 0

    self.packer_pt = CANPacker(DBC[CP.carFingerprint]['pt'])

    self.hcaSameTorqueCount = 0
    self.hcaEnabledFrameCount = 0
    self.graButtonStatesToSend = None
    self.graMsgSentCount = 0
    self.graMsgStartFramePrev = 0
    self.graMsgBusCounterPrev = 0

    self.steer_rate_limited = False

    # global variables for sign-based speed limit recognition
    self.setpoint = 0
    self.targetSetpoint = 0
    self.currentSpeed = 0
    self.speedAdjustInProgress = False
    self.allowNextButtonPress = False
    self.nextStepTimer = 0
    self.smoothAdjust = False
    self.radarDistance = 0
    self.currentSpeedlimit = 0
    self.processedSpeedlimit = -1
    self.wasEngagedBefore = False
    self.done = False


    # options set via settings screen
    self.smooth_adjust_option = Params().get('SmoothSpeedAdjustToggle') == b"1"
    self.ignore_limit_when_difference_too_high = Params().get('IgnoreUnplausibleLimitToggle') == b"1"
    self.ignore_limit_when_following_lead = Params().get('IgnoreLimitLeadToggle') == b"1"

    # configurable offsets

    # these offsets will be applied when OP is not engaged
    self.offsetsNotEngaged = {
                                   0:  {'targetSpeed': 30 },
                                  30:  {'targetSpeed': 30 },
                                  50:  {'targetSpeed': 50 },
                                  60:  {'targetSpeed': 60 },
                                  70:  {'targetSpeed': 70 },
                                  80:  {'targetSpeed': 80 },
                                  100: {'targetSpeed': 100 },
                                  110: {'targetSpeed': 110 },
                                  120: {'targetSpeed': 120 }
                                  }
    # these offsets will be applied when the car is currently slower than a new speedlimit
    self.offsetsAccel = {
                                  0:  {'targetSpeed': 30 },
                                  30:  {'targetSpeed': 30 },
                                  50:  {'targetSpeed': 52 },
                                  60:  {'targetSpeed': 62 },
                                  70:  {'targetSpeed': 72 },
                                  80:  {'targetSpeed': 82 },
                                  100: {'targetSpeed': 103 },
                                  110: {'targetSpeed': 110 },
                                  120: {'targetSpeed': 122 }
                                  }
    # these offsets will be applied when the car is currently faster than a new speedlimit
    self.offsetsDecel = {
                                  50:  {'targetSpeed': 53 },
                                  60:  {'targetSpeed': 64 },
                                  80:  {'targetSpeed': 90 },
                                  100: {'targetSpeed': 103 },
                                  110: {'targetSpeed': 113 },
                                  120: {'targetSpeed': 123 }
                                  }


  def update(self, enabled, CS, frame, actuators, visual_alert, left_lane_visible, right_lane_visible):
    """ Controls thread """

    P = CarControllerParams

    # Send CAN commands.
    can_sends = []

    #--------------------------------------------------------------------------
    #                                                                         #
    # Prepare HCA_01 Heading Control Assist messages with steering torque.    #
    #                                                                         #
    #--------------------------------------------------------------------------

    # The factory camera sends at 50Hz while steering and 1Hz when not. When
    # OP is active, Panda filters HCA_01 from the factory camera and OP emits
    # HCA_01 at 50Hz. Rate switching creates some confusion in Cabana and
    # doesn't seem to add value at this time. The rack will accept HCA_01 at
    # 100Hz if we want to control at finer resolution in the future.
    if frame % P.HCA_STEP == 0:

      # FAULT AVOIDANCE: HCA must not be enabled at standstill. Also stop
      # commanding HCA if there's a fault, so the steering rack recovers.
      if enabled and not (CS.out.standstill or CS.steeringFault):

        # FAULT AVOIDANCE: Requested HCA torque must not exceed 3.0 Nm. This
        # is inherently handled by scaling to STEER_MAX. The rack doesn't seem
        # to care about up/down rate, but we have some evidence it may do its
        # own rate limiting, and matching OP helps for accurate tuning.
        new_steer = int(round(actuators.steer * P.STEER_MAX))
        apply_steer = apply_std_steer_torque_limits(new_steer, self.apply_steer_last, CS.out.steeringTorque, P)
        self.steer_rate_limited = new_steer != apply_steer

        # FAULT AVOIDANCE: HCA must not be enabled for >360 seconds. Sending
        # a single frame with HCA disabled is an effective workaround.
        if apply_steer == 0:
          # We can usually reset the timer for free, just by disabling HCA
          # when apply_steer is exactly zero, which happens by chance during
          # many steer torque direction changes. This could be expanded with
          # a small dead-zone to capture all zero crossings, but not seeing a
          # major need at this time.
          hcaEnabled = False
          self.hcaEnabledFrameCount = 0
        else:
          self.hcaEnabledFrameCount += 1
          if self.hcaEnabledFrameCount >= 118 * (100 / P.HCA_STEP):  # 118s
            # The Kansas I-70 Crosswind Problem: if we truly do need to steer
            # in one direction for > 360 seconds, we have to disable HCA for a
            # frame while actively steering. Testing shows we can just set the
            # disabled flag, and keep sending non-zero torque, which keeps the
            # Panda torque rate limiting safety happy. Do so 3x within the 360
            # second window for safety and redundancy.
            hcaEnabled = False
            self.hcaEnabledFrameCount = 0
          else:
            hcaEnabled = True
            # FAULT AVOIDANCE: HCA torque must not be static for > 6 seconds.
            # This is to detect the sending camera being stuck or frozen. OP
            # can trip this on a curve if steering is saturated. Avoid this by
            # reducing torque 0.01 Nm for one frame. Do so 3x within the 6
            # second period for safety and redundancy.
            if self.apply_steer_last == apply_steer:
              self.hcaSameTorqueCount += 1
              if self.hcaSameTorqueCount > 1.9 * (100 / P.HCA_STEP):  # 1.9s
                apply_steer -= (1, -1)[apply_steer < 0]
                self.hcaSameTorqueCount = 0
            else:
              self.hcaSameTorqueCount = 0

      else:
        # Continue sending HCA_01 messages, with the enable flags turned off.
        hcaEnabled = False
        apply_steer = 0

      self.apply_steer_last = apply_steer
      idx = (frame / P.HCA_STEP) % 16
      can_sends.append(volkswagencan.create_mqb_steering_control(self.packer_pt, CANBUS.pt, apply_steer,
                                                                 idx, hcaEnabled))

    #--------------------------------------------------------------------------
    #                                                                         #
    # Prepare LDW_02 HUD messages with lane borders, confidence levels, and   #
    # the LKAS status LED.                                                    #
    #                                                                         #
    #--------------------------------------------------------------------------

    # The factory camera emits this message at 10Hz. When OP is active, Panda
    # filters LDW_02 from the factory camera and OP emits LDW_02 at 10Hz.

    if frame % P.LDW_STEP == 0:
      hcaEnabled = True if enabled and not CS.out.standstill else False

      if visual_alert == car.CarControl.HUDControl.VisualAlert.steerRequired:
        hud_alert = MQB_LDW_MESSAGES["laneAssistTakeOverSilent"]
      else:
        hud_alert = MQB_LDW_MESSAGES["none"]

      can_sends.append(volkswagencan.create_mqb_hud_control(self.packer_pt, CANBUS.pt, hcaEnabled,
                                                            CS.out.steeringPressed, hud_alert, left_lane_visible,
                                                            right_lane_visible, CS.ldw_lane_warning_left,
                                                            CS.ldw_lane_warning_right, CS.ldw_side_dlc_tlc,
                                                            CS.ldw_dlc, CS.ldw_tlc))

    #--------------------------------------------------------------------------
    #                                                                         #
    # Prepare GRA_ACC_01 ACC control messages with button press events.       #
    #                                                                         #
    #--------------------------------------------------------------------------

    # The car sends this message at 33hz. OP sends it on-demand only for
    # virtual button presses.
    #
    # First create any virtual button press event needed by openpilot, to sync
    # stock ACC with OP disengagement, or to auto-resume from stop.

    if frame > self.graMsgStartFramePrev + P.GRA_VBP_STEP:
      if not enabled and CS.out.cruiseState.enabled:
        # Cancel ACC if it's engaged with OP disengaged.
        self.graButtonStatesToSend = BUTTON_STATES.copy()
        self.graButtonStatesToSend["cancel"] = True
      elif enabled and CS.out.standstill:
        # Blip the Resume button if we're engaged at standstill.
        # FIXME: This is a naive implementation, improve with visiond or radar input.
        # A subset of MQBs like to "creep" too aggressively with this implementation.
        self.graButtonStatesToSend = BUTTON_STATES.copy()
        self.graButtonStatesToSend["resumeCruise"] = True


    #-------------------------------------------------------------------------#
    #      adjust ACC setpoint from sign-based speed limit recognition        #
    #-------------------------------------------------------------------------#

    # this runs 4 times faster than the button press events above because buttons
    # need to be pressed in quick succession to reach the desired ACC setpoint as
    # fast as possible
    if frame > self.graMsgStartFramePrev + P.GRA_VBP_STEP / 4:
      # read current CAN values
      self.radarDistance = CS.radarDistance
      self.currentSpeed = round(CS.out.vEgoRaw * 3.6)
      self.setpoint = round(CS.out.cruiseState.speed * 3.6)
      if not self.speedAdjustInProgress:
        self.currentSpeedlimit = round(CS.trafficSign_01 * 5) # multiplicator probably needs to be changed if using mph instead of kmh
        self.targetSetpoint = 0
        self.nextStepTimer = 0
        self.smoothAdjust = False

      # when engaged use the following 2 routines to adjust the ACC setpoint depending on the current speed
      if enabled and CS.out.cruiseState.enabled and not CS.out.standstill:
        self.wasEngagedBefore = True

        # 1: logic when car is currently faster than speed limit
        if self.currentSpeed > self.currentSpeedlimit and not self.speedAdjustInProgress and self.processedSpeedlimit != self.currentSpeedlimit:
          self.speedAdjustInProgress = True
          self.smoothAdjust = self.smooth_adjust_option

          if self.ignore_limit_when_difference_too_high and self.currentSpeed - self.currentSpeedlimit > 25:
            # ignore speed limit if unplausible speed difference, treat speedlimit as processed
            self.processedSpeedlimit = self.currentSpeedlimit
          elif self.ignore_limit_when_following_lead and self.radarDistance > 0:
            # if currently following another car, adopt the speed of the lead to stay in traffic flow
            self.targetSetpoint = self.currentSpeed + 2
          else:
            # apply the setpoint via the offset table "offsetsDecel"
            if self.currentSpeedlimit in self.offsetsDecel:
              self.targetSetpoint = self.offsetsDecel[self.currentSpeedlimit]['targetSpeed']


        # 2: logic when car is currently slower than speed limit
        if self.currentSpeed < self.currentSpeedlimit and not self.speedAdjustInProgress and self.processedSpeedlimit != self.currentSpeedlimit:
          self.speedAdjustInProgress = True

          if self.ignore_limit_when_difference_too_high and self.currentSpeedlimit - self.currentSpeed > 20 and (self.radarDistance == 0 or self.radarDistance > 80):
            # limit max setpoint increment to 20 if there is no lead car to avoid excessive acceleration
            if self.currentSpeed + 20 < self.currentSpeedlimit and self.currentSpeed + 20 >= 50:
              self.targetSetpoint = self.currentSpeed + 20
          else:
            # apply the setpoint via the offset table "offsetsAccel"
            if self.currentSpeedlimit in self.offsetsAccel:
              self.targetSetpoint = self.offsetsAccel[self.currentSpeedlimit]['targetSpeed']


      # when not engaged, continue to pre-set the acc setpoint to speed limits (like stock pACC does)
      elif not enabled:
        # if OP was engaged before, abort currently running setpoint adjustments
        if self.wasEngagedBefore:
          self.speedAdjustInProgress = False
          self.wasEngagedBefore = False

        if not self.speedAdjustInProgress and self.processedSpeedlimit != self.currentSpeedlimit:
          self.speedAdjustInProgress = True

          if self.currentSpeedlimit in self.offsetsNotEngaged:
            # apply the setpoint via the offset table "offsetsNotEngaged"
            self.targetSetpoint = self.offsetsNotEngaged[self.currentSpeedlimit]['targetSpeed']


      # setpoint adjustment logic
      if self.speedAdjustInProgress and self.setpoint != self.targetSetpoint and self.targetSetpoint > 0 and CS.out.cruiseState.available:
        cur_time = sec_since_boot()

        if self.graMsgSentCount == 0:

          if self.smoothAdjust:
          # if there's more than one button press needed to reach the targetSetpoint, wait after each press until
          # the intermediate setpoint speed is actually reached, resulting in less abrupt slow down
            if abs(self.setpoint - self.currentSpeed) < 3 or (self.currentSpeed < self.setpoint and self.targetSetpoint <= self.currentSpeed) or cur_time > self.nextStepTimer + 10:
              self.allowNextButtonPress = True

          if self.allowNextButtonPress or not self.smoothAdjust:
            self.allowNextButtonPress = False
            self.nextStepTimer = cur_time
            if self.setpoint > self.targetSetpoint:
              self.graButtonStatesToSend = BUTTON_STATES.copy()
              self.graButtonStatesToSend["decelCruise"] = True
            if self.setpoint < self.targetSetpoint and self.targetSetpoint - self.setpoint >= 10:
              self.graButtonStatesToSend = BUTTON_STATES.copy()
              self.graButtonStatesToSend["accelCruise"] = True

          if self.setpoint < self.targetSetpoint and self.targetSetpoint - self.setpoint < 10:
            if enabled:
              self.graButtonStatesToSend = BUTTON_STATES.copy()
              self.graButtonStatesToSend["resumeCruise"] = True
            else:
              # never press the resume button when not engaged, otherwise OP would engage itself in a loop
              # when not engaged, small adjust steps are not possible, abort adjustment process
              self.speedAdjustInProgress = False
              self.processedSpeedlimit = self.currentSpeedlimit
      else:
        self.speedAdjustInProgress = False
        self.processedSpeedlimit = self.currentSpeedlimit


    # OP/Panda can see this message but can't filter it when integrated at the
    # R242 LKAS camera. It could do so if integrated at the J533 gateway, but
    # we need a generalized solution that works for either. The message is
    # counter-protected, so we need to time our transmissions very precisely
    # to achieve fast and fault-free switching between message flows accepted
    # at the J428 ACC radar.
    #
    # Example message flow on the bus, frequency of 33Hz (GRA_ACC_STEP):
    #
    # CAR: 0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F  0  1  2  3  4  5  6
    # EON:        3  4  5  6  7  8  9  A  B  C  D  E  F  0  1  2  GG^
    #
    # If OP needs to send a button press, it waits to see a GRA_ACC_01 message
    # counter change, and then immediately follows up with the next increment.
    # The OP message will be sent within about 1ms of the car's message, which
    # is about 2ms before the car's next message is expected. OP sends for an
    # arbitrary duration of 16 messages / ~0.5 sec, in lockstep with each new
    # message from the car.
    #
    # Because OP's counter is synced to the car, J428 immediately accepts the
    # OP messages as valid. Further messages from the car get discarded as
    # duplicates without a fault. When OP stops sending, the extra time gap
    # (GG) to the next valid car message is less than 1 * GRA_ACC_STEP. J428
    # tolerates the gap just fine and control returns to the car immediately.

    if CS.graMsgBusCounter != self.graMsgBusCounterPrev:
      self.graMsgBusCounterPrev = CS.graMsgBusCounter
      if self.graButtonStatesToSend is not None:
        if self.graMsgSentCount == 0:
          self.graMsgStartFramePrev = frame
        idx = (CS.graMsgBusCounter + 1) % 16
        can_sends.append(volkswagencan.create_mqb_acc_buttons_control(self.packer_pt, CANBUS.pt, self.graButtonStatesToSend, CS, idx))
        self.graMsgSentCount += 1
        if self.graMsgSentCount >= P.GRA_VBP_COUNT:
          self.graButtonStatesToSend = None
          self.graMsgSentCount = 0

    return can_sends
