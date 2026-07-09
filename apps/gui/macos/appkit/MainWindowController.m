#import "MainWindowController.h"
#import "CommandClient.h"

@interface MainWindowController ()
@property(nonatomic, strong) FacManCommandClient *commandClient;
@property(nonatomic, strong) NSTextField *cliPathField;
@property(nonatomic, strong) NSTextField *workspaceField;
@property(nonatomic, strong) NSTextView *resultView;
@property(nonatomic, strong) NSMutableDictionary<NSString *, NSTextField *> *inputFields;
@end

static NSString *FacManStatusText(FacManCommandStatus status);

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
        [self buildLayout];
        [self loadDefaults];
        [self renderText:@"Ready. Configure a facman executable if it is not bundled with this AppKit app."];
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

    NSView *bar = [[NSView alloc] initWithFrame:NSMakeRect(0, height - 72, width, 72)];
    [bar setAutoresizingMask:(NSViewWidthSizable | NSViewMinYMargin)];
    [content addSubview:bar];
    [self addLabel:@"CLI path" toView:bar frame:NSMakeRect(12, 42, 72, 20)];
    self.cliPathField = [self addTextFieldToView:bar key:nil frame:NSMakeRect(88, 38, width - 360, 24) placeholder:@""];
    [self addButton:@"Help" commandId:@"help" toView:bar frame:NSMakeRect(width - 250, 36, 104, 28)];
    [self addButton:@"Version" commandId:@"version" toView:bar frame:NSMakeRect(width - 136, 36, 104, 28)];

    [self addLabel:@"Workspace" toView:bar frame:NSMakeRect(12, 12, 72, 20)];
    self.workspaceField = [self addTextFieldToView:bar key:nil frame:NSMakeRect(88, 8, width - 360, 24) placeholder:@""];
    [self addLabel:@"Transport: CLI JSON" toView:bar frame:NSMakeRect(width - 250, 10, 218, 20)];

    NSTabView *tabs = [[NSTabView alloc] initWithFrame:NSMakeRect(0, 220, width, height - 292)];
    [tabs setAutoresizingMask:(NSViewWidthSizable | NSViewHeightSizable)];
    [content addSubview:tabs];
    [self addDashboardTab:tabs];
    [self addDoctorTab:tabs];
    [self addInstallsTab:tabs];
    [self addInstancesTab:tabs];
    [self addLaunchPlanTab:tabs];
    [self addDiagnosticsTab:tabs];
    [self addSettingsTab:tabs];

    NSScrollView *scroll = [[NSScrollView alloc] initWithFrame:NSMakeRect(0, 0, width, 220)];
    [scroll setAutoresizingMask:(NSViewWidthSizable | NSViewMaxYMargin)];
    [scroll setHasVerticalScroller:YES];
    [scroll setHasHorizontalScroller:YES];
    self.resultView = [[NSTextView alloc] initWithFrame:[[scroll contentView] bounds]];
    [self.resultView setEditable:NO];
    [self.resultView setFont:[NSFont userFixedPitchFontOfSize:12.0]];
    [scroll setDocumentView:self.resultView];
    [content addSubview:scroll];
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
    [self addButton:@"Product Inspect" commandId:@"product.inspect" toView:view frame:NSMakeRect(16, 26, 142, 32)];
    [self addButton:@"Command Graph" commandId:@"command_graph.inspect" toView:view frame:NSMakeRect(168, 26, 142, 32)];
    [self addButton:@"Diagnostics" commandId:@"diagnostics.export" toView:view frame:NSMakeRect(320, 26, 142, 32)];
}

- (void)addDoctorTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Doctor" toTabs:tabs];
    [self addLabel:@"Workspace checks" toView:view frame:NSMakeRect(16, 366, 420, 24)];
    [self addButton:@"Run Doctor" commandId:@"doctor" toView:view frame:NSMakeRect(16, 320, 142, 32)];
    [self addButton:@"Inspect Product" commandId:@"product.inspect" toView:view frame:NSMakeRect(168, 320, 142, 32)];
    [self addButton:@"Command Graph" commandId:@"command_graph.inspect" toView:view frame:NSMakeRect(320, 320, 142, 32)];
}

- (void)addInstallsTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Installs" toTabs:tabs];
    [self addLabel:@"Install commands" toView:view frame:NSMakeRect(16, 366, 420, 24)];
    [self addTextFieldToView:view key:@"installs.scan.scanPath" frame:NSMakeRect(150, 320, 520, 24) placeholder:@"Optional scan root"];
    [self addLabel:@"Scan root" toView:view frame:NSMakeRect(16, 322, 120, 20)];
    [self addButton:@"Scan" commandId:@"installs.scan" toView:view frame:NSMakeRect(690, 318, 132, 30)];

    [self addLabel:@"Install path" toView:view frame:NSMakeRect(16, 282, 120, 20)];
    [self addTextFieldToView:view key:@"installs.import.installPath" frame:NSMakeRect(150, 280, 520, 24) placeholder:@"Existing Factorio folder"];
    [self addLabel:@"Install id" toView:view frame:NSMakeRect(16, 246, 120, 20)];
    [self addTextFieldToView:view key:@"installs.import.installId" frame:NSMakeRect(150, 244, 220, 24) placeholder:@"fixture"];
    [self addButton:@"Import" commandId:@"installs.import" toView:view frame:NSMakeRect(690, 264, 132, 30)];

    [self addLabel:@"Inspect id" toView:view frame:NSMakeRect(16, 204, 120, 20)];
    [self addTextFieldToView:view key:@"installs.inspect.installId" frame:NSMakeRect(150, 202, 220, 24) placeholder:@"fixture"];
    [self addButton:@"Inspect" commandId:@"installs.inspect" toView:view frame:NSMakeRect(690, 200, 132, 30)];
    [self addDeferredButton:@"setup.preview" toView:view frame:NSMakeRect(16, 148, 160, 30)];
}

- (void)addInstancesTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Instances" toTabs:tabs];
    [self addLabel:@"Instance commands" toView:view frame:NSMakeRect(16, 366, 420, 24)];
    [self addButton:@"List" commandId:@"instances.list" toView:view frame:NSMakeRect(16, 320, 132, 30)];
    [self addLabel:@"Instance name" toView:view frame:NSMakeRect(16, 280, 120, 20)];
    [self addTextFieldToView:view key:@"instances.create.instanceName" frame:NSMakeRect(150, 278, 300, 24) placeholder:@"Space Age Main"];
    [self addLabel:@"Install id" toView:view frame:NSMakeRect(16, 244, 120, 20)];
    [self addTextFieldToView:view key:@"instances.create.installId" frame:NSMakeRect(150, 242, 220, 24) placeholder:@"fixture"];
    [self addLabel:@"Template id" toView:view frame:NSMakeRect(16, 208, 120, 20)];
    [self addTextFieldToView:view key:@"instances.create.templateId" frame:NSMakeRect(150, 206, 220, 24) placeholder:@"vanilla"];
    [self addButton:@"Create" commandId:@"instances.create" toView:view frame:NSMakeRect(470, 240, 132, 30)];
}

- (void)addLaunchPlanTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Launch Plan" toTabs:tabs];
    [self addLabel:@"Launch plan commands" toView:view frame:NSMakeRect(16, 366, 420, 24)];
    [self addLabel:@"Instance id" toView:view frame:NSMakeRect(16, 322, 120, 20)];
    [self addTextFieldToView:view key:@"launch.instanceId" frame:NSMakeRect(150, 320, 260, 24) placeholder:@"space-age-main"];
    [self addButton:@"Build Plan" commandId:@"launch_plan.build" toView:view frame:NSMakeRect(430, 318, 132, 30)];
    [self addButton:@"Preview Run" commandId:@"run.preview" toView:view frame:NSMakeRect(572, 318, 132, 30)];
    [self addDeferredButton:@"run.execute" toView:view frame:NSMakeRect(16, 268, 160, 30)];
}

- (void)addDiagnosticsTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Diagnostics" toTabs:tabs];
    [self addLabel:@"Diagnostics and deferred package commands" toView:view frame:NSMakeRect(16, 366, 420, 24)];
    [self addButton:@"Export Diagnostics" commandId:@"diagnostics.export" toView:view frame:NSMakeRect(16, 320, 160, 30)];
    [self addDeferredButton:@"modsets.lock" toView:view frame:NSMakeRect(16, 270, 160, 30)];
    [self addDeferredButton:@"saves.backup" toView:view frame:NSMakeRect(186, 270, 160, 30)];
    [self addDeferredButton:@"export.instance" toView:view frame:NSMakeRect(356, 270, 160, 30)];
    [self addDeferredButton:@"import.instance" toView:view frame:NSMakeRect(526, 270, 160, 30)];
}

- (void)addSettingsTab:(NSTabView *)tabs
{
    NSView *view = [self addTab:@"Settings/About" toTabs:tabs];
    NSTextView *info = [[NSTextView alloc] initWithFrame:NSMakeRect(16, 130, 940, 250)];
    [info setEditable:NO];
    [info setString:@"FACMAN-APPKIT-SHELL-01\n\nThis app is a thin AppKit frontend over the shared FacMan command graph.\nIt renders required command results returned by the configured backend path and keeps deferred commands disabled or refused with reasons.\n\nIt does not implement Factorio discovery logic, setup mutation, Mod Portal network access, modset resolution, save/export/import behavior, server execution, developer execution, credential storage, or direct Factorio launch behavior in Objective-C."];
    [view addSubview:info];
    [self addButton:@"Run Help" commandId:@"help" toView:view frame:NSMakeRect(16, 80, 132, 30)];
    [self addButton:@"Run Version" commandId:@"version" toView:view frame:NSMakeRect(158, 80, 132, 30)];
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
    [view addSubview:field];
    if (key != nil) {
        [self.inputFields setObject:field forKey:key];
    }
    return field;
}

- (void)addLabel:(NSString *)text toView:(NSView *)view frame:(NSRect)frame
{
    NSTextField *label = [[NSTextField alloc] initWithFrame:frame];
    [label setStringValue:text];
    [label setEditable:NO];
    [label setBezeled:NO];
    [label setDrawsBackground:NO];
    [view addSubview:label];
}

- (void)addButton:(NSString *)title commandId:(NSString *)commandId toView:(NSView *)view frame:(NSRect)frame
{
    NSButton *button = [[NSButton alloc] initWithFrame:frame];
    [button setTitle:title];
    [button setButtonType:NSButtonTypeMomentaryPushIn];
    [button setBezelStyle:NSBezelStyleRounded];
    [button setTarget:self];
    [button setAction:@selector(runCommand:)];
    [button setIdentifier:commandId];
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
    NSDictionary<NSString *, NSString *> *inputs = [self inputsForCommandId:commandId];
    FacManCommandResult *result = [self.commandClient executeCommandId:commandId
                                                                inputs:inputs
                                                             workspace:[self.workspaceField stringValue]
                                                               cliPath:[self.cliPathField stringValue]];
    [self renderText:[result displayText]];
}

- (NSDictionary<NSString *, NSString *> *)inputsForCommandId:(NSString *)commandId
{
    NSMutableDictionary<NSString *, NSString *> *inputs = [NSMutableDictionary dictionary];
    if ([commandId isEqualToString:@"installs.scan"]) {
        [self copyInput:@"installs.scan.scanPath" toKey:@"scanPath" into:inputs];
    } else if ([commandId isEqualToString:@"installs.import"]) {
        [self copyInput:@"installs.import.installPath" toKey:@"installPath" into:inputs];
        [self copyInput:@"installs.import.installId" toKey:@"installId" into:inputs];
    } else if ([commandId isEqualToString:@"installs.inspect"]) {
        [self copyInput:@"installs.inspect.installId" toKey:@"installId" into:inputs];
    } else if ([commandId isEqualToString:@"instances.create"]) {
        [self copyInput:@"instances.create.instanceName" toKey:@"instanceName" into:inputs];
        [self copyInput:@"instances.create.installId" toKey:@"installId" into:inputs];
        [self copyInput:@"instances.create.templateId" toKey:@"templateId" into:inputs];
    } else if ([commandId isEqualToString:@"launch_plan.build"] || [commandId isEqualToString:@"run.preview"]) {
        [self copyInput:@"launch.instanceId" toKey:@"instanceId" into:inputs];
    }
    return inputs;
}

- (void)copyInput:(NSString *)fieldKey toKey:(NSString *)inputKey into:(NSMutableDictionary<NSString *, NSString *> *)inputs
{
    NSTextField *field = [self.inputFields objectForKey:fieldKey];
    if (field != nil) {
        [inputs setObject:[field stringValue] forKey:inputKey];
    }
}

- (void)loadDefaults
{
    NSString *cli = [[[NSProcessInfo processInfo] environment] objectForKey:@"FACMAN_CLI"];
    if ([cli length] > 0) {
        [self.cliPathField setStringValue:cli];
    }
    NSString *workspace = [[[NSProcessInfo processInfo] environment] objectForKey:@"FACMAN_WORKSPACE"];
    if ([workspace length] > 0) {
        [self.workspaceField setStringValue:workspace];
    }
}

- (void)renderText:(NSString *)text
{
    [self.resultView setString:text ?: @""];
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
