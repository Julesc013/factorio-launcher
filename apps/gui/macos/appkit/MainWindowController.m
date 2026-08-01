// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import "MainWindowController.h"
#import "CommandClient.h"
#import "FacManGeneratedCommandCatalog.h"
#import "FacManLivePresentation.h"
#import "FacManPreviewFixture.h"

@interface MainWindowController ()
@property(nonatomic, strong) FacManCommandClient *commandClient;
@property(nonatomic, strong) NSTextField *cliPathField;
@property(nonatomic, strong) NSTextField *workspaceField;
@property(nonatomic, strong) NSTextView *resultView;
@property(nonatomic, strong) NSMutableDictionary<NSString *, NSTextField *> *inputFields;
@property(nonatomic, strong) NSPopUpButton *commandPopup;
@property(nonatomic, strong) NSTabView *productTabs;
@property(nonatomic, strong) NSTextField *pageTitle;
@property(nonatomic, strong) NSTextField *pageSummary;
@property(nonatomic, strong) NSTextField *deckStatus;
@property(nonatomic, strong) NSTextField *deckReadiness;
@property(nonatomic, strong) NSTextField *deckLastRun;
@property(nonatomic, strong) NSTextField *deckOperation;
@property(nonatomic, strong) NSButton *deckPrimary;
@property(nonatomic, strong) NSButton *deckSecondary;
@property(nonatomic, strong) NSBox *launchDeck;
@property(nonatomic, strong) NSPopUpButton *appearancePopup;
@property(nonatomic, strong) FacManPreviewFixture *fixture;
@property(nonatomic, strong) FacManLivePresentation *livePresentation;
@property(nonatomic, assign) BOOL evidenceMode;
@property(nonatomic, strong) NSTextField *instanceSummaryLabel;
@property(nonatomic, strong) NSTextField *installationSummaryLabel;
@property(nonatomic, strong) NSMutableArray<NSButton *> *evidenceButtons;
@property(nonatomic, copy) NSString *retainedLastRun;
@property(nonatomic, assign) BOOL relaunched;
@end

static NSString *FacManStatusText(FacManCommandStatus status);
static NSString *FacManVisualizationTitle(NSString *renderer);

@implementation MainWindowController

- (instancetype)init
{
    NSRect frame = NSMakeRect(0, 0, 1080, 720);
    NSWindow *window = [[NSWindow alloc] initWithContentRect:frame
                                                   styleMask:(NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable | NSWindowStyleMaskMiniaturizable)
                                                     backing:NSBackingStoreBuffered
                                                       defer:NO];
    [window setTitle:@"FacMan AppKit Shell"];
    self = [super initWithWindow:window];
    if (self) {
        _commandClient = [[FacManCommandClient alloc] init];
        _inputFields = [NSMutableDictionary dictionary];
        _fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateReady];
        _livePresentation = [[FacManLivePresentation alloc] initWithCommandClient:_commandClient];
        NSString *presentationMode = [[[NSProcessInfo processInfo] environment] objectForKey:@"FACMAN_PRESENTATION_MODE"];
        _evidenceMode = presentationMode != nil && [presentationMode caseInsensitiveCompare:@"evidence"] == NSOrderedSame;
        _evidenceButtons = [NSMutableArray array];
        [self buildLayout];
        [self loadDefaults];
        [self renderFixture];
        if (!_evidenceMode) [self refreshLivePresentation];
    }
    return self;
}

- (void)buildLayout
{
    NSView *content = [[NSView alloc] initWithFrame:[[self window] contentView].bounds];
    [content setAutoresizingMask:(NSViewWidthSizable | NSViewHeightSizable)];
    [[self window] setContentView:content];

    CGFloat width = NSWidth([content bounds]);
    CGFloat height = NSHeight([content bounds]);

    self.productTabs = [[NSTabView alloc] initWithFrame:NSMakeRect(12, 190, width - 24, height - 202)];
    [self.productTabs setAutoresizingMask:(NSViewWidthSizable | NSViewHeightSizable)];
    [content addSubview:self.productTabs];
    [self addInstancesPage];
    [self addInstallationsPage];
    [self addActivityPage];
    [self addSettingsPage];
    [self addAdvancedPage];

    NSBox *deck = [[NSBox alloc] initWithFrame:NSMakeRect(12, 12, width - 24, 166)];
    self.launchDeck = deck;
    [deck setAutoresizingMask:(NSViewWidthSizable | NSViewMaxYMargin)];
    [deck setTitle:self.evidenceMode
        ? @"Launch Deck — EXPLICIT EVIDENCE / DEVELOPMENT MODE"
        : @"Launch Deck — LIVE BACKEND MODE"];
    [deck setAccessibilityLabel:@"Persistent Launch Deck for selected instance C1 Vanilla"];
    [content addSubview:deck];
    self.deckStatus = [self addLabel:@"" toView:deck frame:NSMakeRect(16, 110, 480, 24)];
    [self.deckStatus setFont:[NSFont boldSystemFontOfSize:14.0]];
    self.deckReadiness = [self addLabel:@"" toView:deck frame:NSMakeRect(16, 82, 620, 22)];
    self.deckLastRun = [self addLabel:@"" toView:deck frame:NSMakeRect(16, 54, 620, 22)];
    self.deckOperation = [self addLabel:@"" toView:deck frame:NSMakeRect(16, 26, 620, 22)];
    self.deckPrimary = [self addActionButton:@"Play" selector:@selector(invokePrimary:) toView:deck frame:NSMakeRect(width - 298, 82, 250, 34)];
    self.deckSecondary = [self addActionButton:@"Make readiness stale" selector:@selector(invokeSecondary:) toView:deck frame:NSMakeRect(width - 298, 40, 250, 30)];
    [self.deckPrimary setKeyEquivalent:@"\r"];
}

- (void)addInstancesPage
{
    NSView *view = [self addTab:@"Instances" toTabs:self.productTabs];
    [self addLabel:@"Instances" toView:view frame:NSMakeRect(20, 350, 360, 28)];
    self.instanceSummaryLabel = [self addLabel:@"Inspecting backend instances…" toView:view frame:NSMakeRect(20, 300, 760, 26)];
    [self addActionButton:@"Create instance…" selector:@selector(createFixtureInstance:) toView:view frame:NSMakeRect(20, 250, 180, 32)];
    [self addActionButton:@"Select C1 Vanilla" selector:@selector(selectFixtureInstance:) toView:view frame:NSMakeRect(212, 250, 180, 32)];
}

- (void)addInstallationsPage
{
    NSView *view = [self addTab:@"Installations" toTabs:self.productTabs];
    [self addLabel:@"Installations" toView:view frame:NSMakeRect(20, 350, 360, 28)];
    self.installationSummaryLabel = [self addLabel:@"Inspecting backend installations…" toView:view frame:NSMakeRect(20, 300, 760, 26)];
    [self addActionButton:@"Scan for installations" selector:@selector(rescanFixture:) toView:view frame:NSMakeRect(20, 250, 200, 32)];
}

- (void)addActivityPage
{
    NSView *view = [self addTab:@"Activity" toTabs:self.productTabs];
    self.pageTitle = [self addLabel:@"Activity" toView:view frame:NSMakeRect(20, 350, 360, 28)];
    self.pageSummary = [self addLabel:@"" toView:view frame:NSMakeRect(20, 300, 760, 26)];
    NSButton *finish = [self addActionButton:@"Finish fixture run" selector:@selector(finishFixture:) toView:view frame:NSMakeRect(20, 250, 180, 32)];
    NSButton *interrupt = [self addActionButton:@"Simulate interruption" selector:@selector(interruptFixture:) toView:view frame:NSMakeRect(212, 250, 180, 32)];
    [self.evidenceButtons addObjectsFromArray:@[ finish, interrupt ]];
}

- (void)addSettingsPage
{
    NSView *view = [self addTab:@"Settings / About" toTabs:self.productTabs];
    [self addLabel:@"FacMan 0.1 C1 classic preview" toView:view frame:NSMakeRect(20, 350, 520, 28)];
    [self addLabel:(self.evidenceMode
        ? @"EXPLICIT EVIDENCE / DEVELOPMENT MODE · unchanged deterministic fixtures · no live Play authority"
        : @"LIVE BACKEND MODE · bounded process RPC · backend-gated exact Play route · preview support lane")
             toView:view frame:NSMakeRect(20, 312, 900, 24)];
    [self addLabel:@"Appearance" toView:view frame:NSMakeRect(20, 260, 120, 24)];
    self.appearancePopup = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(150, 256, 220, 30) pullsDown:NO];
    [self.appearancePopup addItemsWithTitles:@[ @"System Native", @"FacMan OEM+ Launch Deck" ]];
    [self.appearancePopup setTarget:self];
    [self.appearancePopup setAction:@selector(changeAppearance:)];
    [self.appearancePopup setAccessibilityLabel:@"Appearance mode"];
    [view addSubview:self.appearancePopup];
}

- (void)addAdvancedPage
{
    NSView *view = [self addTab:@"Advanced" toTabs:self.productTabs];
    [self addLabel:@"Bounded process RPC command explorer" toView:view frame:NSMakeRect(16, 360, 420, 24)];
    [self addLabel:@"Generated categories include Snapshots, Profiles, Servers, recovery, and diagnostics."
             toView:view frame:NSMakeRect(450, 360, 520, 24)];
    [self addLabel:@"CLI path" toView:view frame:NSMakeRect(16, 324, 72, 20)];
    [self addLabel:@"Transport: CLI JSON" toView:view frame:NSMakeRect(620, 324, 180, 20)];
    self.cliPathField = [self addTextFieldToView:view key:nil frame:NSMakeRect(96, 320, 500, 24) placeholder:@""];
    [self addLabel:@"Workspace" toView:view frame:NSMakeRect(16, 292, 72, 20)];
    self.workspaceField = [self addTextFieldToView:view key:nil frame:NSMakeRect(96, 288, 500, 24) placeholder:@""];
    self.commandPopup = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(16, 246, 360, 28) pullsDown:NO];
    for (FacManCommandDefinition *command in [FacManCommandClient catalog]) {
        [self.commandPopup addItemWithTitle:command.commandId];
        [[self.commandPopup lastItem] setRepresentedObject:command.commandId];
    }
    [self.commandPopup setAccessibilityLabel:@"Advanced generated command"];
    [view addSubview:self.commandPopup];
    [self addActionButton:@"Run command" selector:@selector(runSelectedCommand:) toView:view frame:NSMakeRect(388, 244, 140, 32)];
    NSScrollView *scroll = [[NSScrollView alloc] initWithFrame:NSMakeRect(16, 12, 940, 220)];
    [scroll setHasVerticalScroller:YES];
    self.resultView = [[NSTextView alloc] initWithFrame:[[scroll contentView] bounds]];
    [self.resultView setEditable:NO];
    [self.resultView setFont:[NSFont userFixedPitchFontOfSize:12.0]];
    [self.resultView setAccessibilityLabel:@"Advanced command result"];
    [scroll setDocumentView:self.resultView];
    [view addSubview:scroll];
}

- (void)addDashboardTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Dashboard" toTabs:tabs];
    [self addLabel:@"Shared command graph surface" toView:view frame:NSMakeRect(16, 366, 420, 24)];
    NSTextView *catalog = [[NSTextView alloc] initWithFrame:NSMakeRect(16, 74, 1000, 284)];
    [catalog setEditable:NO];
    [catalog setFont:[NSFont userFixedPitchFontOfSize:11.0]];
    NSMutableString *text = [NSMutableString string];
    for (FacManCommandDefinition *command in [FacManCommandClient catalog]) {
        [text appendFormat:@"%@ -> %@ [%@]\n", command.commandId, command.backendId, FacManStatusText(command.status)];
        if ([command.deferredReason length] > 0) {
            [text appendFormat:@"  %@\n", command.deferredReason];
        }
    }
    [catalog setString:text];
    [view addSubview:catalog];
    self.commandPopup = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(16, 28, 360, 28) pullsDown:NO];
    for (FacManCommandDefinition *command in [FacManCommandClient catalog]) {
        [self.commandPopup addItemWithTitle:command.commandId];
        [[self.commandPopup lastItem] setRepresentedObject:command.commandId];
    }
    [view addSubview:self.commandPopup];
    NSButton *open = [[NSButton alloc] initWithFrame:NSMakeRect(388, 26, 142, 32)];
    [open setTitle:@"Open Command"];
    [open setTarget:self];
    [open setAction:@selector(runSelectedCommand:)];
    [view addSubview:open];
}

- (void)addDoctorTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Doctor" toTabs:tabs];
    [self addLabel:@"Workspace checks" toView:view frame:NSMakeRect(16, 366, 420, 24)];
    [self addButton:@"Run Doctor" commandId:@"doctor.run" toView:view frame:NSMakeRect(16, 320, 142, 32)];
    [self addButton:@"Inspect Product" commandId:@"product.inspect" toView:view frame:NSMakeRect(168, 320, 142, 32)];
    [self addButton:@"Explain Doctor" commandId:@"doctor.explain" toView:view frame:NSMakeRect(320, 320, 142, 32)];
}

- (void)addInstallsTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Installs" toTabs:tabs];
    NSTextView *workflow = [[NSTextView alloc] initWithFrame:NSMakeRect(16, 210, 1000, 180)];
    [workflow setEditable:NO];
    [workflow setFont:[NSFont userFixedPitchFontOfSize:11.0]];
    [workflow setString:FacManGeneratedSetupWorkflowText()];
    [workflow setAccessibilityLabel:@"Managed portable setup workflow"];
    [view addSubview:workflow];
    [self addGeneratedCommandsToView:view prefixes:@[ @"install_refs.", @"installs.", @"setup." ] startY:190];
}

- (void)addInstancesTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Instances" toTabs:tabs];
    [self addGeneratedCommandsToView:view prefixes:@[ @"instance." ]];
}

- (void)addLaunchPlanTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Launch Plan" toTabs:tabs];
    [self addGeneratedCommandsToView:view prefixes:@[ @"launch_plan.", @"run." ]];
}

- (void)addDiagnosticsTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Diagnostics" toTabs:tabs];
    [self addGeneratedCommandsToView:view prefixes:@[ @"diagnostics.", @"dev." ]];
}

- (void)addGeneratedTab:(NSString *)title prefixes:(NSArray<NSString *> *)prefixes toTabs:(NSTabView *)tabs
{
    NSView *view = [self addTab:title toTabs:tabs];
    [self addGeneratedCommandsToView:view prefixes:prefixes];
}

- (void)addGeneratedCommandsToView:(NSView *)view prefixes:(NSArray<NSString *> *)prefixes
{
    [self addGeneratedCommandsToView:view prefixes:prefixes startY:350];
}

- (void)addGeneratedCommandsToView:(NSView *)view prefixes:(NSArray<NSString *> *)prefixes startY:(NSInteger)startY
{
    NSInteger index = 0;
    for (FacManCommandDefinition *command in [FacManCommandClient catalog]) {
        BOOL included = NO;
        for (NSString *prefix in prefixes) if ([command.backendId hasPrefix:prefix]) included = YES;
        if (!included) continue;
        NSInteger column = index % 3;
        NSInteger row = index / 3;
        NSRect frame = NSMakeRect(16 + column * 320, startY - row * 48, 300, 34);
        [self addButton:command.label commandId:command.commandId toView:view frame:frame];
        index++;
    }
}

- (void)addSettingsTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Settings/About" toTabs:tabs];
    NSTextView *info = [[NSTextView alloc] initWithFrame:NSMakeRect(16, 130, 940, 250)];
    [info setEditable:NO];
    [info setString:
        @"FACMAN-APPKIT-SHELL-01\n\n"
        @"This app is a thin AppKit frontend over the shared FacMan command graph.\n"
        @"It renders required command results returned by the configured backend path "
        @"and keeps deferred commands disabled or refused with reasons.\n\n"
        @"It does not implement Factorio discovery logic, setup mutation, Mod Portal network access, "
        @"modset resolution, save/export/import behavior, server execution, developer execution, "
        @"credential storage, or direct Factorio launch behavior in Objective-C."];
    [view addSubview:info];
    [self addButton:@"Workspace Paths" commandId:@"workspace.paths" toView:view frame:NSMakeRect(16, 80, 132, 30)];
    [self addButton:@"Capabilities" commandId:@"capabilities.inspect" toView:view frame:NSMakeRect(158, 80, 132, 30)];
}

- (NSView *)addTab:(NSString *)title toTabs:(NSTabView *)tabs
{
    NSTabViewItem *item = [[NSTabViewItem alloc] initWithIdentifier:title];
    [item setLabel:title];
    NSView *view = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 1040, 420)];
    [item setView:view];
    [tabs addTabViewItem:item];
    return view;
}

- (NSTextField *)addTextFieldToView:(NSView *)view key:(NSString *)key frame:(NSRect)frame placeholder:(NSString *)placeholder
{
    NSTextField *field = [[NSTextField alloc] initWithFrame:frame];
    [field setStringValue:placeholder ?: @""];
    [field setAccessibilityLabel:key ?: @"Path or command input"];
    [view addSubview:field];
    if (key != nil) {
        [self.inputFields setObject:field forKey:key];
    }
    return field;
}

- (NSTextField *)addLabel:(NSString *)text toView:(NSView *)view frame:(NSRect)frame
{
    NSTextField *label = [[NSTextField alloc] initWithFrame:frame];
    [label setStringValue:text];
    [label setEditable:NO];
    [label setBezeled:NO];
    [label setDrawsBackground:NO];
    [label setAccessibilityLabel:text];
    [view addSubview:label];
    return label;
}

- (NSButton *)addActionButton:(NSString *)title selector:(SEL)selector toView:(NSView *)view frame:(NSRect)frame
{
    NSButton *button = [[NSButton alloc] initWithFrame:frame];
    [button setTitle:title];
    [button setButtonType:NSButtonTypeMomentaryPushIn];
    [button setBezelStyle:NSBezelStyleRounded];
    [button setTarget:self];
    [button setAction:selector];
    [button setAccessibilityLabel:title];
    [button setAccessibilityHelp:self.evidenceMode
        ? @"Explicit evidence/development fixture action; no live process is started."
        : @"Backend-derived action over bounded process RPC; backend admission remains authoritative."];
    [view addSubview:button];
    return button;
}

- (void)renderFixture
{
    FacManPreviewState state = self.evidenceMode ? self.fixture.state : self.livePresentation.state;
    NSString *statusText = self.evidenceMode ? self.fixture.statusText : self.livePresentation.statusText;
    NSString *readiness = self.evidenceMode ? self.fixture.readiness : self.livePresentation.readiness;
    NSString *primaryLabel = self.evidenceMode ? self.fixture.primaryLabel : self.livePresentation.primaryLabel;
    NSString *primaryAccessibilityLabel = self.evidenceMode ? self.fixture.primaryAccessibilityLabel : self.livePresentation.primaryAccessibilityLabel;
    NSString *activitySummary = self.evidenceMode ? self.fixture.activitySummary : self.livePresentation.activitySummary;
    NSString *operation = self.evidenceMode ? self.fixture.operationId : self.livePresentation.operationId;
    NSString *lastRun = self.evidenceMode
        ? ([self.retainedLastRun length] > 0 ? self.retainedLastRun : self.fixture.lastRun)
        : self.livePresentation.lastRun;
    [self.deckStatus setStringValue:statusText];
    [self.deckReadiness setStringValue:[@"Readiness: " stringByAppendingString:readiness]];
    [self.deckLastRun setStringValue:[@"Last Run: " stringByAppendingString:lastRun]];
    if (self.evidenceMode && self.relaunched && state == FacManPreviewStateRunning) operation = @"operation.fixture-play-002";
    [self.deckOperation setStringValue:[operation length] > 0
        ? [@"Operation: " stringByAppendingString:operation]
        : @"Operation: none"];
    [self.deckPrimary setTitle:primaryLabel];
    [self.deckPrimary setAccessibilityLabel:primaryAccessibilityLabel];
    [self.deckPrimary setEnabled:self.evidenceMode ? self.fixture.primaryEnabled : self.livePresentation.primaryEnabled];
    NSString *secondary = self.evidenceMode ? @"Make readiness stale" : @"Refresh backend state";
    if (state == FacManPreviewStateStaleReadiness) secondary = @"Rescan readiness";
    if (state == FacManPreviewStateInterrupted) secondary = @"Recover operation";
    [self.deckSecondary setTitle:secondary];
    [self.deckSecondary setAccessibilityLabel:secondary];
    [self.pageSummary setStringValue:activitySummary];
    if (!self.evidenceMode) {
        [self.instanceSummaryLabel setStringValue:self.livePresentation.instanceSummary ?: @""];
        [self.installationSummaryLabel setStringValue:self.livePresentation.installationSummary ?: @""];
    }
    for (NSButton *button in self.evidenceButtons) [button setHidden:!self.evidenceMode];
    NSAccessibilityPostNotification(self.deckStatus, NSAccessibilityValueChangedNotification);
}

- (void)invokePrimary:(id)sender
{
    (void)sender;
    if (!self.evidenceMode) {
        if (self.livePresentation.recoveryRequired) { [self showActivity:nil]; return; }
        if (!self.livePresentation.primaryEnabled) {
            NSAlert *alert = [[NSAlert alloc] init];
            [alert setMessageText:self.livePresentation.refusalCode ?: @"Play unavailable"];
            [alert setInformativeText:self.livePresentation.refusalDetail ?: @"Backend did not enable Play."];
            [alert addButtonWithTitle:@"OK"];
            [alert runModal];
            return;
        }
        [self.deckPrimary setEnabled:NO];
        [self.livePresentation playWithWorkspace:[self.workspaceField stringValue]
                                         cliPath:[self.cliPathField stringValue]
                                      completion:^{ [self renderFixture]; }];
        return;
    }
    switch (self.fixture.state) {
        case FacManPreviewStateStaleReadiness: {
            NSAlert *alert = [[NSAlert alloc] init];
            [alert setMessageText:@"Readiness changed"];
            [alert setInformativeText:@"stale_readiness — Play was refused before effects because observed revision 7 is stale; current revision is 8. Rescan readiness before retrying."];
            [alert addButtonWithTitle:@"OK"];
            [alert runModal];
            break;
        }
        case FacManPreviewStateRunning:
            [self showActivity:nil];
            break;
        case FacManPreviewStateInterrupted:
            [self showActivity:nil];
            break;
        case FacManPreviewStateExited:
            self.relaunched = YES;
            self.fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateRunning];
            [self renderFixture];
            break;
        case FacManPreviewStateReady:
        default:
            self.relaunched = NO;
            self.fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateRunning];
            [self renderFixture];
            break;
    }
}

- (void)invokeSecondary:(id)sender
{
    (void)sender;
    if (!self.evidenceMode) {
        if (self.livePresentation.recoveryRequired) {
            [self.livePresentation recoverWithWorkspace:[self.workspaceField stringValue]
                                                 cliPath:[self.cliPathField stringValue]
                                              completion:^{ [self renderFixture]; }];
        } else {
            [self refreshLivePresentation];
        }
        return;
    }
    if (self.fixture.state == FacManPreviewStateInterrupted) {
        [self recoverFixture:nil];
    } else if (self.fixture.state == FacManPreviewStateStaleReadiness) {
        [self rescanFixture:nil];
    } else {
        [self loadStaleFixture:nil];
    }
}

- (void)loadStaleFixture:(id)sender
{
    (void)sender;
    self.fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateStaleReadiness];
    [self renderFixture];
}

- (void)rescanFixture:(id)sender
{
    (void)sender;
    if (!self.evidenceMode) { [self refreshLivePresentation]; return; }
    self.fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateReady];
    [self renderFixture];
}

- (void)finishFixture:(id)sender
{
    (void)sender;
    if (!self.evidenceMode) return;
    if (self.fixture.state != FacManPreviewStateRunning) return;
    self.retainedLastRun = self.relaunched
        ? @"Exited normally · code 0 · operation.fixture-play-002"
        : @"Exited normally · code 0 · operation.fixture-play-001";
    self.fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateExited];
    [self renderFixture];
}

- (void)interruptFixture:(id)sender
{
    (void)sender;
    if (!self.evidenceMode) return;
    self.retainedLastRun = @"Interrupted · outcome unknown · operation.fixture-play-001";
    self.fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateInterrupted];
    [self renderFixture];
    [self showActivity:nil];
}

- (void)recoverFixture:(id)sender
{
    (void)sender;
    if (!self.evidenceMode) { [self invokeSecondary:nil]; return; }
    if (self.fixture.state != FacManPreviewStateInterrupted) return;
    self.fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateReady];
    [self renderFixture];
}

- (void)createFixtureInstance:(id)sender
{
    (void)sender;
    if (!self.evidenceMode) { [self runCommandId:@"instances.create" sender:nil]; return; }
    self.fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateReady];
    [self renderFixture];
}

- (void)selectFixtureInstance:(id)sender
{
    (void)sender;
    if (!self.evidenceMode) { [self refreshLivePresentation]; return; }
    self.fixture = [FacManPreviewFixture fixtureForState:FacManPreviewStateReady];
    [self renderFixture];
}

- (void)refreshLivePresentation
{
    [self.deckStatus setStringValue:@"Inspecting workspace, installations, instances, readiness, Activity, Last Run, and recovery…"];
    [self.livePresentation refreshWithWorkspace:[self.workspaceField stringValue]
                                        cliPath:[self.cliPathField stringValue]
                                     completion:^{ [self renderFixture]; }];
}

- (void)changeAppearance:(id)sender
{
    (void)sender;
    if ([self.appearancePopup indexOfSelectedItem] == 0) {
        [self.launchDeck setTransparent:YES];
    } else {
        [self.launchDeck setBoxType:NSBoxCustom];
        [self.launchDeck setTransparent:NO];
        [self.launchDeck setFillColor:[NSColor colorWithCalibratedRed:0.84 green:0.90 blue:0.98 alpha:1.0]];
    }
}

- (void)restoreSystemNative:(id)sender
{
    (void)sender;
    [self.appearancePopup selectItemAtIndex:0];
    [self changeAppearance:nil];
}

- (void)showInstances:(id)sender { (void)sender; [self.productTabs selectTabViewItemAtIndex:0]; }
- (void)showInstallations:(id)sender { (void)sender; [self.productTabs selectTabViewItemAtIndex:1]; }
- (void)showActivity:(id)sender { (void)sender; [self.productTabs selectTabViewItemAtIndex:2]; }
- (void)showSettingsAbout:(id)sender { (void)sender; [self.productTabs selectTabViewItemAtIndex:3]; }
- (void)showAdvanced:(id)sender { (void)sender; [self.productTabs selectTabViewItemAtIndex:4]; }

- (void)addButton:(NSString *)title commandId:(NSString *)commandId toView:(NSView *)view frame:(NSRect)frame
{
    NSButton *button = [[NSButton alloc] initWithFrame:frame];
    [button setTitle:title];
    [button setButtonType:NSButtonTypeMomentaryPushIn];
    [button setBezelStyle:NSBezelStyleRounded];
    [button setTarget:self];
    [button setAction:@selector(runCommand:)];
    [button setIdentifier:commandId];
    [button setAccessibilityLabel:title];
    [button setAccessibilityHelp:[NSString stringWithFormat:@"Run generated command %@", commandId]];
    [view addSubview:button];
}

- (void)addDeferredButton:(NSString *)commandId toView:(NSView *)view frame:(NSRect)frame
{
    FacManCommandDefinition *command = [FacManCommandClient definitionForCommandId:commandId];
    NSButton *button = [[NSButton alloc] initWithFrame:frame];
    [button setTitle:commandId];
    [button setEnabled:NO];
    [button setToolTip:command.deferredReason];
    [view addSubview:button];
}

- (void)runCommand:(id)sender
{
    NSString *commandId = [sender identifier];
    [self runCommandId:commandId sender:sender];
}

- (void)runSelectedCommand:(id)sender
{
    (void)sender;
    NSString *commandId = [[self.commandPopup selectedItem] representedObject];
    [self runCommandId:commandId sender:nil];
}

- (void)cancelCommand:(id)sender
{
    (void)sender;
    [self.commandClient cancelCurrentCommand];
    [self renderText:@"Cancellation requested."];
}

- (void)runCommandId:(NSString *)commandId sender:(id)sender
{
    FacManCommandDefinition *command = [FacManCommandClient definitionForCommandId:commandId];
    BOOL cancelled = NO;
    NSDictionary<NSString *, NSString *> *inputs = [self generatedInputsForCommand:command cancelled:&cancelled];
    if (cancelled) return;
    [self renderText:[NSString stringWithFormat:@"Running %@...", commandId]];
    if (sender != nil) [sender setEnabled:NO];
    [self.commandClient executeCommandId:commandId
                                  inputs:inputs
                               workspace:[self.workspaceField stringValue]
                                 cliPath:[self.cliPathField stringValue]
                              completion:^(FacManCommandResult *result) {
                                  [self renderText:[NSString stringWithFormat:@"View: %@\nRisk: %@\nEffects: %@\n\n%@",
                                      FacManVisualizationTitle(command.renderer), command.riskTier, command.effects,
                                      [result displayText]]];
                                  if (sender != nil) [sender setEnabled:YES];
                                  if (!self.evidenceMode && [commandId isEqualToString:@"instances.create"] && !result.refused)
                                      [self refreshLivePresentation];
                              }];
}

- (NSDictionary<NSString *, NSString *> *)generatedInputsForCommand:(FacManCommandDefinition *)command
                                                         cancelled:(BOOL *)cancelled
{
    if (cancelled != NULL) *cancelled = NO;
    if (command == nil || command.status != FacManCommandStatusImplemented) return @{};
    NSData *data = [command.inputDefinitions dataUsingEncoding:NSUTF8StringEncoding];
    NSArray<NSDictionary *> *fields = data == nil ? @[] : [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    if ([fields count] == 0) return @{};
    NSAlert *alert = [[NSAlert alloc] init];
    [alert setMessageText:command.label];
    [alert setInformativeText:[NSString stringWithFormat:@"Availability: %@ | Risk: %@ | Effects: %@",
        command.availability, command.riskTier, command.effects]];
    [alert addButtonWithTitle:(command.dryRunDefault ? @"Run" : @"Apply")];
    [alert addButtonWithTitle:@"Cancel"];
    CGFloat height = MAX(60.0, [fields count] * 42.0);
    NSView *form = [[NSView alloc] initWithFrame:NSMakeRect(0, 0, 520, height)];
    NSMutableDictionary<NSString *, NSControl *> *controls = [NSMutableDictionary dictionary];
    NSInteger index = 0;
    for (NSDictionary *field in fields) {
        NSString *key = [field objectForKey:@"key"];
        BOOL required = [[field objectForKey:@"required"] boolValue];
        CGFloat y = height - 34 - index * 42;
        [self addLabel:[key stringByAppendingString:(required ? @" *" : @"")]
                 toView:form
                  frame:NSMakeRect(0, y + 2, 150, 22)];
        NSString *type = [field objectForKey:@"type"];
        NSControl *control = nil;
        NSArray *choices = [field objectForKey:@"choices"];
        if ([choices count] > 0) {
            NSPopUpButton *popup = [[NSPopUpButton alloc] initWithFrame:NSMakeRect(160, y, 350, 26) pullsDown:NO];
            if (!required) [popup addItemWithTitle:@""];
            [popup addItemsWithTitles:choices];
            control = popup;
        } else if ([type isEqualToString:@"boolean"]) {
            NSButton *toggle = [[NSButton alloc] initWithFrame:NSMakeRect(160, y, 330, 24)];
            [toggle setButtonType:NSSwitchButton];
            [toggle setTitle:@"Enabled"];
            control = toggle;
        } else if ([type isEqualToString:@"path"]) {
            NSPathControl *path = [[NSPathControl alloc] initWithFrame:NSMakeRect(160, y, 350, 26)];
            [path setPathStyle:NSPathStyleStandard];
            control = path;
        } else {
            NSTextField *text = [[NSTextField alloc] initWithFrame:NSMakeRect(160, y, 350, 24)];
            NSString *defaultValue = [field objectForKey:@"default"];
            if ([defaultValue isKindOfClass:[NSString class]]) [text setStringValue:defaultValue];
            control = text;
        }
        [form addSubview:control];
        [control setAccessibilityLabel:key];
        [control setAccessibilityHelp:[NSString stringWithFormat:@"%@ %@ field", required ? @"Required" : @"Optional", type]];
        [controls setObject:control forKey:key];
        index++;
    }
    [alert setAccessoryView:form];
    if ([alert runModal] != NSAlertFirstButtonReturn) {
        if (cancelled != NULL) *cancelled = YES;
        return @{};
    }
    NSMutableDictionary<NSString *, NSString *> *inputs = [NSMutableDictionary dictionary];
    for (NSDictionary *field in fields) {
        NSString *key = [field objectForKey:@"key"];
        NSControl *control = [controls objectForKey:key];
        NSString *value = @"";
        if ([control isKindOfClass:[NSPathControl class]]) {
            value = [[(NSPathControl *)control URL] path] ?: @"";
        } else if ([control isKindOfClass:[NSButton class]]) {
            value = [(NSButton *)control state] == NSControlStateValueOn ? @"true" : @"false";
        } else if ([control isKindOfClass:[NSPopUpButton class]]) {
            value = [(NSPopUpButton *)control titleOfSelectedItem] ?: @"";
        } else if ([control isKindOfClass:[NSTextField class]]) {
            value = [(NSTextField *)control stringValue];
        }
        [inputs setObject:value forKey:key];
    }
    return inputs;
}

- (void)loadDefaults
{
    NSString *cli = [[[NSProcessInfo processInfo] environment] objectForKey:@"FACMAN_CLI"];
    if ([cli length] > 0) {
        [self.cliPathField setStringValue:cli];
    }
    [self.workspaceField setStringValue:@""];
}

- (void)renderText:(NSString *)text
{
    [self.resultView setString:text ?: @""];
    NSAccessibilityPostNotification(self.resultView, NSAccessibilityValueChangedNotification);
}

@end

static NSString *FacManStatusText(FacManCommandStatus status)
{
    if (status == FacManCommandStatusImplemented) {
        return @"implemented";
    }
    if (status == FacManCommandStatusStubbedWithRefusal) {
        return @"stubbed_with_refusal";
    }
    return @"not_supported_with_reason";
}

static NSString *FacManVisualizationTitle(NSString *renderer)
{
    if ([renderer hasPrefix:@"instance_diff"]) return @"Instance diff";
    if ([renderer hasPrefix:@"snapshots_"]) return @"Snapshot list or diff";
    if ([renderer hasPrefix:@"modsets_"]) return @"Modset plan graph";
    if ([renderer hasPrefix:@"saves_"]) return @"Save index or retention plan";
    if ([renderer hasPrefix:@"servers_"]) return @"Server plan";
    if ([renderer containsString:@"recovery"] || [renderer containsString:@"transaction"])
        return @"Transaction and recovery state";
    return @"Structured command result";
}
